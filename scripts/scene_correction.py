from openai import OpenAI
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config import OPENAI_API_KEY as API_KEY, ARENA_USERNAME, ARENA_SCENE_NAME
import time
from utils.capture_screenshot import capture_screenshot, get_bounding_box, open_page, close_page, save_login_state, STATE_FILE, get_object_ids
import asyncio
from threading import Lock
import base64


updating_lock = Lock()

def image_to_base64(image_path):
    # Read the image file as binary
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()

    # Convert the binary data to Base64
    image_base64 = base64.b64encode(image_data).decode("utf-8")
    return image_base64

def answer_question(overall_prompt, system_prompt, image_path):
    client = OpenAI(api_key=API_KEY)
    if image_path:
        response = client.chat.completions.create(
            model = "gpt-4o",
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [
                                {
                                    "type": "text",
                                    "text": overall_prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_to_base64(image_path)}"
                                    }
                                }

                            ]
                }
            ],
            max_tokens=4000,
        )
    else:
        response = client.chat.completions.create(
            model = "gpt-4o",
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": overall_prompt
                }
            ],
            max_tokens=4000,
        )
    response = response.choices[0]
    return response.message.content


arena_scene_url = f"https://arenaxr.org/{ARENA_USERNAME}/{ARENA_SCENE_NAME}"
camera_selector = "#my-camera"
screenshot_lock = Lock()
global playwright, browser, context, page


async def async_init():
    global playwright, browser, context, page
    # Open page
    playwright, browser, context, page = await open_page(arena_scene_url)
    # Save login state if not already saved
    if not os.path.exists(STATE_FILE):
        await save_login_state(page, arena_scene_url)
    await asyncio.sleep(5)  # Allow time for the scene to load



async def get_screenshot(page):

    bounding_boxes = dict()
    bounding_box_tasks = []

    object_ids = await get_object_ids(page)
    for object_id in object_ids:
        if object_id not in ['groundPlane', 'cameraRig', 'env', 'ambient-light', 'point-light']:
        
                try:
                    
                    # Schedule the bounding box task without awaiting immediately
                    task = asyncio.create_task(get_bounding_box(page, object_id))
                    bounding_box_tasks.append((object_id, task))  # Store task with object ID
                    
                except Exception as e:
                    print(f"Error scheduling bounding box for {object_id}: {e}")
    
    # Wait for all bounding box tasks to complete
    results = await asyncio.gather(*[task for _, task in bounding_box_tasks], return_exceptions=True)
    
    # Process the results
    global_min = [0, 0, 0]
    global_max = [0, 0, 0]
    
    for (object_id, _), result in zip(bounding_box_tasks, results):
        if isinstance(result, Exception):
            print(f"Error in bounding box task for {object_id}: {result}")
        else:
            bounding_boxes[object_id] = result
            min_coords = result["min"]
            max_coords = result["max"]
            for i in range(3):
                global_min[i] = min(global_min[i], min_coords[i])
                global_max[i] = max(global_max[i], max_coords[i])
    


    #camera coordinate so the entire scene is visible based on size of objects
    position = [(global_min[i] + global_max[i]) / 2 for i in range(3)]
    position[2] = global_max[2] + 5

    rotation = [0, 0, 0]

    await capture_screenshot(page, camera_selector, position, rotation, output_file_prefix="screenshot_python")

    return bounding_boxes

system_prompt_python = """
You are a helpful asssitant whos job is to look at the code of a 3D scene that another LLM generated based on a text prompt and check whether it has been generated correctly.
Your job is to correct the scene constantly so that it looks as close to the prompt as possible.
I will also give you an image of what you generated looks like so you can use it to better correct the scene.
When you update the script, make sure you give me the entire python script with the change added in.
Do not change the object_id or the scene name.
Give only python script and no extra information. Do not add additional quotes or anything else. Do not say the word python.
If there is nothing to correct, just say "None" as the very first word. And if none, justify why there is no change needed on the next line. Make sure in this case that None is the only word on the first line of the response. This is absolutely necessary for parsing.
This includes the position, orientation, and scale of the objects in the scene.
For example, if the prompt was to place a lamp on a table and you see that the table is floating in the air, you should move the table to the ground. 
You should also make sure that the lamp is on the table and not hovering and is in scaled appropriately to the table.
"""

def scene_correction_python(current_running_scripts, memory, arena_python_queue, exception):
    loop = asyncio.new_event_loop()  # Create a new event loop
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_init())


    while True:
            # if not user_prompt_inputted.locked():
            if len(memory) > 0:
                if len(exception) > 0:
                    print("An error occurred in the last execution, attempting to fix it...")
                    exception_input = "The code you generated for me, which is currently running has the following errors: " + str(exception) + " Please give me new code to fix it."
                    overall_prompt =f"""
                        Current Script Running in the scene:
                        {current_running_scripts}
                        History of Prompts(first prompt is the oldest and the last prompt is the latest):
                        {memory}
                        
                        {exception_input}
                    """
                    answer = answer_question(overall_prompt, system_prompt_python, None)
                
                else:
                    #lock and get the screenshot
                    screenshot_lock.acquire()
                    bounding_boxes = loop.run_until_complete(get_screenshot(page))
                    screenshot_lock.release()
                    
                    overall_prompt = f"""
                    Based on the following context, decide whether to modify the scene or not. If you decide to modify the scene, provide the python script of the corrected scene and nothing else:

                    Current Script Running in the scene:
                    {current_running_scripts}

                    Scene Object Bounding Boxes [format = objectid: min: minimum xyz coordinate, max: maximum xyz coordinate] (if the bounding box is inf that means the model is bad and should be replaced. If it uses a model that results in inf, the model should be replaced with primitives):
                    {bounding_boxes}

                    History of Prompts(first prompt is the most recent):
                    {memory}

                    Use the image and the information to correct the scene.
                    """
                    
                    answer = answer_question(overall_prompt, system_prompt_python, "screenshot_python.png")

                if "None" not in answer.splitlines()[0]:
                    if "`" in answer:
                        #remove the first and last line of the response
                        answer = answer.split("\n")
                        answer = answer[1:-1]
                        answer = "\n".join(answer)

                    arena_python_queue.put(answer)
                else:
                    # print("No changes needed.")
                    pass
            time.sleep(5)