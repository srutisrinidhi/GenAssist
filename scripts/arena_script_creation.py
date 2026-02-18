import time
import os
import sys
import json
import base64
import threading
import multiprocessing
import logging
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_classic.retrievers import MultiQueryRetriever
from openai import OpenAI

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config import OPENAI_API_KEY as API_KEY, ARENA_SCENE_NAME

sys.path.append(os.path.join(os.path.dirname(__file__), 'create_databases'))
from create_3D_model_db import load_model_db, find_closest_model

persistent_directory_python = r"./arena_python_docs"

# Load the embedding and LLM model
embeddings_model = OpenAIEmbeddings(openai_api_key=API_KEY, model="text-embedding-ada-002")
llm = ChatOpenAI(model_name="gpt-4o", max_tokens=4096, openai_api_key=API_KEY)
client = OpenAI(api_key=API_KEY)

arena_python_queue = multiprocessing.Queue()

object_ids = set()

user_prompt_inputted = threading.Lock()

# memory = dict()
memory = []

current_scene_objects = dict()
#All of the objects that have already been generated and their corresponding JSONs are contained in this memory dictionary: {memory}.
system_prompt_python = \
f"""
You are an assistant that generates python.
Use the input documents to define the format for the python.
Do not include any additional fields that are not present in the given input documents.
You don't need to have all the fields in the input documents in your output. Every object must have an object_id field.
Give only the code and no extra information. Do not add additional quotes or anything else. Do not say the word python.
Only output the python code. Use scene name {ARENA_SCENE_NAME}
Remember to define objects globally when needed in mulitple functions.
All rotation values should be quaternion values!!
Make everything look as realistic as possible, especially colors and movements.
If there is a + or a # in any of the object id's or titles then change it to plus or hash.
Color Attributes should be used like this Usage: color=Color(red,green,blue) or color=(red,green,blue). DO NOT USE HEX CODES.

I am also giving you the code of any script that is currently running. This is useful if your task is to edit something that already exists.
Remember to regenerate the entire script even if you just edit one line.

Make everything look as realistic as possible, especially colors and movements. Make sure to use the correct object types and attributes.
Also remember that there is no physics engine that I am running, so you have to write all your functions manually.
If you do not know how to handle a user action (Like spray water, or turn on a light), just create a button with that label and assume clicking that button is doing the action.
The labels often tend to end up inside the buttons, can you either make a UI card with a butten or make sure the label is outside the button.
Make everything above the ground!

Here are some examples of prompts and the python script that should be generated:

1. Prompt: Create a box at 0,4,-2 that is 2x2x2 in size.
Python Script:
from arena import *

scene = Scene(host="arenaxr.org", scene="{ARENA_SCENE_NAME}")

def main():
    # make a box
    box = Box(object_id="my_box", position=Position(0,4,-2), scale=Scale(2,2,2))
    print(box.json())
    # add the box
    scene.add_object(box)

# add and start tasks
scene.run_once(main)
scene.run_tasks()


2. Prompt: Create a box which when clicked on moves a few units to the right.
Python Script:
from arena import *

# setup library
scene = Scene(host="arenaxr.org", scene="{ARENA_SCENE_NAME}")

@scene.run_async
async def func():
    # make a box
    box = Box(object_id="my_box", position=Position(0,4,-2), scale=Scale(2,2,2))
    scene.add_object(box)

    def mouse_handler(scene, evt, msg):
        if evt.type == "mousedown":
            box.data.position.x += 0.5
            scene.update_object(box)

    # add click_listener
    scene.update_object(box, click_listener=True, evt_handler=mouse_handler)

# start tasks
scene.run_tasks()

3. Prompt: Create a box and a texst above it saying "Welcome to arena-py" and have them both constantly move to the right slowly.
Python Script:
from arena import *

# setup library
scene = Scene(host="arenaxr.org", scene="{ARENA_SCENE_NAME}")

# make a box
box = Box(object_id="my_box", position=Position(0,4,-2), scale=Scale(2,2,2))

@scene.run_once
def main():
    # add the box
    scene.add_object(box)

    # add text
    text = Text(object_id="my_text", value="Welcome to arena-py!", position=Position(0,2,0), parent=box)
    scene.add_object(text)

x = 0
@scene.run_forever(interval_ms=500)
def periodic():
    global x    # non allocated variables need to be global
    box.update_attributes(position=Position(x,3,0))
    scene.update_object(box)
    x += 0.1

# start tasks
scene.run_tasks()

4. Prompt: Create a script that draws a line behind the camera as the camera moves around in the scene.
Python Script:
from arena import *
import random

MIN_DISPLACEMENT = 0.5
LINE_TTL = 5

class CameraState(Object):
    def __init__(self, camera):
        self.camera = camera
        self.prev_pos = None
        self.line_color = Color(
                random.randint(0,255),
                random.randint(0,255),
                random.randint(0,255)
            )

    @property
    def curr_pos(self):
        # camera position is not static, it is constantly changing and will be updated in real-time
        return self.camera.data.position

    @property
    def displacement(self):
        if self.prev_pos:
            # Position attributes have a distance_to method that returns the distance to another Position
            return self.prev_pos.distance_to(self.curr_pos)
        else:
            return 0

cam_states = []

# called whenever a user is found by the library
def user_join_callback(scene, cam, msg):
    global cam_states

    cam_state = CameraState(cam)
    cam_states += [cam_state]

scene = Scene(host="arenaxr.org", scene="{ARENA_SCENE_NAME}")
scene.user_join_callback = user_join_callback

@scene.run_forever(interval_ms=200)
def line_follow():
    for cam_state in cam_states:
        if cam_state.displacement >= MIN_DISPLACEMENT:
            line = ThickLine(
                    color=cam_state.line_color,
                    path=(cam_state.prev_pos, cam_state.curr_pos),
                    lineWidth=3,
                    ttl=LINE_TTL
                )
            scene.add_object(line)

        # the camera's position gets automatically updated by arena-py!
        cam_state.prev_pos = cam_state.curr_pos

scene.run_tasks()

5. Prompt: Create a house.
    from arena import *

    scene = Scene(host="arenaxr.org", scene="{ARENA_SCENE_NAME}")

    # Create front wall
    front_wall = Box(
        object_id="house_front_wall",
        position=Position(0, 2, 0),
        rotation=Rotation(1, 0, 0, 0),
        depth=1,
        height=4,
        width=5,
        material=Material(color="#986a44"),
    )

    # Create right wall
    right_wall = Box(
        object_id="house_right_wall",
        position=Position(2, 2, -2),
        rotation=Rotation(0.70711, 0, 0.70711, 0),
        depth=1,
        height=4,
        width=5,
        material=Material(color="#986a44"),
    )

    # Create left wall
    left_wall = Box(
        object_id="house_left_wall",
        position=Position(-2, 2, -2),
        rotation=Rotation(0.70711, 0, -0.70711, 0),
        depth=1,
        height=4,
        width=5,
        material=Material(color="#986a44"),
    )

    # Create back wall
    back_wall = Box(
        object_id="house_back_wall",
        position=Position(0, 2, -4),
        rotation=Rotation(1, 0, 0, 0),
        depth=1,
        height=4,
        width=5,
        material=Material(color="#986a44"),
    )

    # Create roof
    roof = Tetrahedron(
        object_id="house_roof",
        position=Position(0, 5, -2),
        rotation=Rotation(-0.6424613459443065,-0.0024350750076095606,-0.6269589110604435,  0.4406359191203554),
        radius=4,
        material=Material(color="#c01c28"),
    )

    # Create door
    door = Box(
        object_id="house_door",
        position=Position(0, 1, 0.6),
        rotation=Rotation(1, 0, 0, 0),
        depth=0.2,
        height=2,
        width=1,
        material=Material(color="#c01c28"),
    )

    @scene.run_once
    def make_house():
        scene.add_object(front_wall)
        scene.add_object(right_wall)
        scene.add_object(left_wall)
        scene.add_object(back_wall)
        scene.add_object(roof)
        scene.add_object(door)

    scene.run_tasks()



Knowing this, here is my question:

""".replace("\n", " ")



def image_to_base64(image_path):
    # Read the image file as binary
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()

    # Convert the binary data to Base64
    image_base64 = base64.b64encode(image_data).decode("utf-8")
    return image_base64



def load_database_and_retriever(persistant_directory):
    vectordb = Chroma(persist_directory=persistant_directory, embedding_function = embeddings_model)

    # Embedding with distance retriver
    # retriever = vectordb.as_retriever(search_kwargs = {"k" : 2})

    # #LLM retriver
    retriever = MultiQueryRetriever.from_llm(
        retriever=vectordb.as_retriever(), llm=llm)
    return retriever


def answer_question(overall_prompt, system_prompt):
    client = OpenAI(api_key=API_KEY)
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
                            }

                        ]
            }
        ],
        max_tokens=4000,
    )
    response = response.choices[0]
    return response.message.content


def ask(question, to_retrieve, retriever, system_prompt, model_db, current_running_scripts, prompt_history_python):
    unique_docs = retriever.invoke(to_retrieve)
    #retrive model
    models = find_closest_model(to_retrieve, model_db)
    if len(models) > 0:
        print("models = ", models)
        for closest_model in models:
            if closest_model.endswith(".gltf") or closest_model.endswith(".glb"):
                model_type = "gltf-model"
            elif closest_model.endswith(".obj"):
                model_type = "obj-model"
            model_to_send = f"Object Gerenation Information: Here is a list of 3D models that you might find helpful to answer the question:{models}. If you end up using the model, set persist = false and remember the object type should be {model_type}. If you use the model, make sure to use the URL correctly and not make one up. Only use this if you can't create the object with primitives that arena can already make. \n"
    else:
        model_to_send = "Object Generation Information: Use primitives to create the object.\n"
    # closest_memory = find_closest_memory(to_retrieve, memory)
    closest_memory = [[""]]
    #                

    overall_prompt = f"""
        You are a 3D scene generation assistant. Based on the following context, generate code to create the specified scene:

        1. Relevant Documentation:
        {unique_docs}

        2. Available 3D Models:
        {model_to_send}

        3. Current Scripts that are Running:
        {current_running_scripts}

        4. History of prompts (first one is the most recent):
        {prompt_history_python}

        Generate the code considering the above context for the question that follows: {question + to_retrieve}

    """
    #         4. Current objects in the scene that may be related to your task:
    #    {closest_memory}
    print("Overall Prompt:", overall_prompt)
    answer = answer_question(overall_prompt, system_prompt)

    # num_memory_entries = len(closest_memory[0])

    memory_ids = [] # an array of sets consisting of object ids for each memory
    memory_strs = []
    # print("Closest memory is")
    # print(closest_memory)
    # for i in range(num_memory_entries):
    #     comma_split = []
    #     curr_object_ids = set()
    #     curr_ids_str = ""
    #     for line in closest_memory[0][i].split(";"):
    #         comma_split = line.split(',')
    #         curr_object_ids.add(comma_split[0][14:-1])
    #         curr_ids_str = curr_ids_str + comma_split[0][14:-1] + " "
    #     memory_ids.append(curr_object_ids)
    #     memory_strs.append(curr_ids_str[:-1])

    return answer, memory_ids, memory_strs

terminal_input = None

def get_input():
    global terminal_input
    while True:
        terminal_input = input("What object(s) should I make in the ARENA? \n> ")






def create_python_from_instruction(current_running_scripts, prompt_history_python, chat_input):
    global terminal_input
    print("Loading Vector Database...", end=" ")

    retriever = load_database_and_retriever(persistent_directory_python)
    model_db = load_model_db("model_db")
    # Start the input function in a new thread
    thread = threading.Thread(target=get_input, daemon=True)
    thread.start()
    print("Database Loaded!")
    print()
    print("Hello, I am an assistant that can create ARENA objects!")
    print()

    while True:
        if len(chat_input) == 0:
            if terminal_input is None:
                time.sleep(1)
                continue
            else:
                user_input = terminal_input
                terminal_input = None
        else:
            user_input = chat_input[-1]
            chat_input.pop()

        print("On it! Hang on...", user_input)

        user_question = "Give python code to "
        answer, memory_ids, memory_strs = ask(user_question, user_input, retriever, system_prompt_python, model_db, current_running_scripts, prompt_history_python)
        print("Response:")
        human_readable_response = answer.replace(";", "\n")
        print(human_readable_response)
        if "`" in answer:

            #remove the first and last line of the response
            answer = answer.split("\n")
            answer = answer[1:-1]
            answer = "\n".join(answer)

        arena_python_queue.put(answer)
        prompt_history_python.insert(0,user_input)



def testing_python_from_instruction(current_running_scripts, prompt_history_python, chat_input):
    global terminal_input
    print("Loading Vector Database...", end=" ")

    retriever = load_database_and_retriever(persistent_directory_python)
    model_db = load_model_db("model_db")
    # Start the input function in a new thread
    thread = threading.Thread(target=get_input, daemon=True)
    thread.start()
    print("Database Loaded!")
    print()
    print("Hello, I am an assistant that can create ARENA objects!")
    print()

    with open("test_cases/empty_scene.txt", "r") as f:
        lines = [line.strip() for line in f.readlines()]

    line_index = 0

    # while True:
    #     if len(chat_input) == 0:
    #         if terminal_input is None:
    #             time.sleep(1)
    #             continue
    #         else:
    #             user_input = terminal_input
    #             terminal_input = None
    #     else:
    #         user_input = chat_input[-1]
    #         chat_input.pop()
    # else:
    #     user_prompt_inputted.acquire()
    while line_index < len(lines):
        current_running_scripts = []

        input("Press Enter to use the next input...")

        user_input = lines[line_index]
        print(f"> {user_input}")  

        print("On it! Hang on...", user_input)

        user_question = "Give python code to "
        answer, memory_ids, memory_strs = ask(user_question, user_input, retriever, system_prompt_python, model_db, current_running_scripts, prompt_history_python)

        print("Response:")
        human_readable_response = answer.replace(";", "\n")
        print(human_readable_response)
        if "`" in answer:

            #remove the first and last line of the response
            answer = answer.split("\n")
            answer = answer[1:-1]
            answer = "\n".join(answer)


        arena_python_queue.put(answer)
        prompt_history_python.insert(0,user_input)
        while True:
            success = input("Did it work? (yes/no) ").strip().lower()
            if success in ["yes", "no"]:
                break  
            else:
                print("Please enter 'yes' or 'no'.")

        # Ask for additional notes
        notes = input("Any additional notes? (Press Enter to skip) ").strip()

        # Open files here
        with open("results.txt", "a") as results_file, open("notes.txt", "a") as notes_file:
            results_file.write(success + "\n")
            notes_file.write(notes + "\n")

        line_index += 1  

