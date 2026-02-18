# GenAssist: Interactive Prompt-Driven XR Program Generation

**IEEE VR '26**

[[Paper]](https://github.com/srutisrinidhi/GenAssist/blob/main/docs/assets/GenAssist_full.pdf) [[Website]](https://www.srutisrinidhi.com/GenAssist/) [[Demo Paper]](https://github.com/srutisrinidhi/GenAssist/blob/main/docs/assets/demo_paper.pdf) [[Video]](https://youtu.be/nA28_u0hOjU)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/srutisrinidhi/GenAssist.git
cd GenAssist
```

### 2. Create a conda environment

```bash
conda create -n genassist python=3.10
conda activate genassist
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your OpenAI API key

Open `config.py` and replace the placeholder with your key:

```python
OPENAI_API_KEY = "your-api-key-here"
```

### 5. Clone the ARENA Python library

```bash
git clone https://github.com/arenaxr/arena-py
```

### 6. Create the ARENA documentation database

```bash
python scripts/create_databases/create_arena_docs_db.py
```

### 7. Upload your 3D models to the ARENA file store

GenAssist retrieves 3D models from your personal ARENA file store. To set this up:

1. Create a free account at [arenaxr.org](https://arenaxr.org)
2. Upload your 3D models (`.glb` or `.gltf` format) to your file store. Your models will be available at:
   ```
   https://arenaxr.org/store/users/<your-username>/
   ```
   You can upload via the [ARENA build page](https://arenaxr.org/build) — under **Add/Edit Object**, select type `GLTF Model`, then click **Upload File & Publish**. See the [file store docs](https://docs.arenaxr.org/content/interface/filestore.html) for more details.
3. Update `ARENA_STORE_URL` in `config.py` with your username:
   ```python
   ARENA_STORE_URL = "https://arenaxr.org/store/users/<your-username>/"
   ```

### 8. Create the 3D model database

```bash
python scripts/create_databases/create_3D_model_db.py
```

### 9. Set your ARENA scene

Open `config.py` and set your ARENA username and a name for your scene:

```python
ARENA_USERNAME = "your-arenaxr-username"
ARENA_SCENE_NAME = "ai_scene_python"  # or any scene name you like
```

Your scene will be accessible at:
```
https://arenaxr.org/<your-username>/<your-scene-name>
```

The scene is created automatically the first time you connect. You can view it in any browser or XR headset.

## Running GenAssist

```bash
python scripts/main.py
```

On first run, a browser window will open and prompt you to authenticate with your ARENA account. Once logged in, the session is saved and future runs will not require re-authentication.

After startup, GenAssist will print:
```
Hello, I am an assistant that can create ARENA objects!
```

You can then describe what you want to create in two ways:
- **Terminal**: Type your prompt directly in the terminal
- **ARENA chat**: Send a chat message in the ARENA scene at `https://arenaxr.org/<your-username>/<your-scene-name>`

GenAssist will generate the scene, run it, and continuously self-correct it based on visual feedback.

Press `Ctrl+C` to stop.

## Optional: Sketchfab Model Search

If you want GenAssist to search and download models from Sketchfab, add your Sketchfab API token to `config.py`:

```python
SKETCHFAB_API_KEY = "your-sketchfab-api-key-here"
```

You can get a free API token at [sketchfab.com/settings/password](https://sketchfab.com/settings/password).

To search for a model:

```python
import sys
sys.path.append("scripts/utils")
from sketchfab_models import search_and_download_gltf
from config import SKETCHFAB_API_KEY

downloaded = search_and_download_gltf("chair", SKETCHFAB_API_KEY, "./models")
```
