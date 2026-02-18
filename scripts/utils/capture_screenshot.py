import asyncio
from playwright.async_api import async_playwright
import os
import sys
import base64

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from config import ARENA_USERNAME, ARENA_SCENE_NAME

# File to store login state
STATE_FILE = "auth_state.json"

# Open a browser and page with the saved login state
async def open_page(url):
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(storage_state=STATE_FILE if os.path.exists(STATE_FILE) else None)
    page = await context.new_page()
    # Navigate to the URL
    await page.goto(url)
    return playwright, browser, context, page

# Close the browser and cleanup
async def close_page(playwright, browser):
    await browser.close()
    await playwright.stop()

# Save login state
async def save_login_state(page, arena_url):
    print(f"Opening ARENA scene: {arena_url}")
    await page.goto(arena_url)

    try:
        await page.fill('#usernameInput', "test")
        await page.click('#anonBtn')
        await page.click('#enterSceneAVBtn')
    except Exception as e:
        print(f"Automatic login failed: {e}")
        await page.wait_for_timeout(30000)  # Allow manual login if automated login fails

    # Save login state to a file
    await page.context.storage_state(path=STATE_FILE)
    print(f"Login state saved to {STATE_FILE}")


async def get_object_ids(page):
    #go into the page and get the object ids
    object_ids = await page.evaluate('''() => {
        const sceneRoot = document.querySelector("#sceneRoot");
        if (!sceneRoot) {
            throw new Error("sceneRoot not found in the scene.");
        }
        return Array.from(sceneRoot.children)
            .filter(obj => !obj.hasAttribute("arena-user")) // Exclude objects with arena_user
            .map(obj => obj.id)
            .filter(id => id); // Ensure no empty IDs
    }''')
    return object_ids

# Get 3D bounding box of an object
async def get_bounding_box(page, object_id):
    try:
        box = await page.evaluate(f'''() => {{
            const box = new THREE.Box3();
            box.setFromObject(document.getElementById("{object_id}").object3D);
            console.log(box.max, box.min);
            return {{
                min: box.min.toArray().map(num => parseFloat(num.toFixed(2))),
                max: box.max.toArray().map(num => parseFloat(num.toFixed(2)))
            }};
        }}''')
        return box
    except Exception as e:
        print(f"Failed to get bounding box for object '{object_id}': {e}")
        return None

# Capture screenshots
async def capture_screenshot(page, camera_selector, position, rotation, output_file_prefix="screenshot"):
    try:
        await page.wait_for_selector("a-scene", timeout=600000)


        # Inject the screenshot component if not present
        await page.evaluate('''() => {
            if (!AFRAME.components.screenshot) {
                const script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/gh/aframevr/aframe@master/dist/components/screenshot.min.js';
                document.head.appendChild(script);
            }
        }''')
        
        
        await page.wait_for_timeout(2000)
        # Set the desired camera as the active camera
        await page.evaluate(f'''() => {{
            const cameraEntity = document.querySelector("{camera_selector}");
            if (!cameraEntity) {{
                throw new Error("Camera with selector '{camera_selector}' not found.");
            }}
            cameraEntity.setAttribute('position', {{
                x: {position[0]}, 
                y: {position[1]}, 
                z: {position[2]}
            }});
            cameraEntity.setAttribute('rotation', {{
                x: {rotation[0]}, 
                y: {rotation[1]}, 
                z: {rotation[2]}
            }});
            const scene = document.querySelector("a-scene");
            scene.camera = cameraEntity.getObject3D('camera');
        }}''')

        # Capture screenshot
        screenshot_data_url = await page.evaluate('''() => {
            const scene = document.querySelector('a-scene');
            if (scene && scene.components && scene.components.screenshot) {
                scene.components.screenshot.capture('perspective');
                return scene.components.screenshot.getCanvas('perspective').toDataURL();
            } else {
                throw new Error('Screenshot component could not be injected or is unavailable.');
            }
        }''')

        # Save the screenshot
        base64_data = screenshot_data_url.split(",")[1]
        output_file = f"{output_file_prefix}.png"
        with open(output_file, "wb") as f:
            f.write(base64.b64decode(base64_data))
    except Exception as e:
        print(f"Failed to capture screenshot: {e}")

# Main function to test the modularized approach
async def main():
    arena_scene_url = f"https://arenaxr.org/{ARENA_USERNAME}/{ARENA_SCENE_NAME}"
    camera_selector = "#my-camera"

    # Open page
    playwright, browser, context, page = await open_page(arena_scene_url)

    # Save login state if not already saved
    if not os.path.exists(STATE_FILE):
        save_login_state(page, arena_scene_url)

    # Perform actions
    await capture_screenshot(page, camera_selector)

    # Close page
    await close_page(playwright, browser)

if __name__ == "__main__":
    asyncio.run(main())
