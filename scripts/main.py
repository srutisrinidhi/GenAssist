from arena import *
from arena_script_creation import arena_python_queue, create_python_from_instruction
from scene_correction import scene_correction_python
from threading import Thread
import multiprocessing
import time
import sys
import os
import traceback

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config import ARENA_SCENE_NAME


camera_selector = "#my-camera"


current_running_scripts = []
prompt_history = []


get_chat_code = f"""
import arena


def chat_handler(_scene, chatmsg, _rawmsg):
    print(f"Chat Message:{{chatmsg.text.strip()}}")

scene = arena.Scene(host="arenaxr.org", scene="{ARENA_SCENE_NAME}", on_chat_callback=chat_handler)

scene.run_tasks()
"""

class LiveOutput:
    """A wrapper around sys.stdout to print and capture output at the same time."""
    def __init__(self, chat_input, exception):
        self.output = []  # Stores all captured output
        self.chat_input = chat_input
        self.exception = exception

    def write(self, message):
        if "does not match topic" in message:
            return
        sys.__stdout__.write(message)  # Print to actual stdout in real-time
        self.output.append(message)    # Store the message
        if "Something went wrong!" in message:
            # sys.__stdout__.write("Error: " + message)
            self.exception.append(message)
            sys.__stdout__.write("Error: " + str(self.exception))
        if "Chat Message:" in message:
            self.chat_input.append(message.split(":")[1])
            # print("Chat Message: " + self.chat_input[-1])

    def flush(self):
        sys.__stdout__.flush()  # Ensure real-time output

def run_code(python_code, exception, chat_input):

    live_output = LiveOutput(chat_input, exception)
    ##reset exception
    exception[:] = []

    sys.stdout = live_output   # Redirect stdout to our custom class

    try:
        exec(python_code, globals())  # Run the user code
    except Exception:
        exception.append(traceback.format_exc())  # Capture full traceback of the error
        print(exception)  # Ensure error is printed in real-time

    # Restore original stdout
    sys.stdout = sys.__stdout__
    
    return "".join(live_output.output), exception  # Return captured output and any errors


if __name__ == '__main__':
    # Set start method before creating Manager or any processes
    try:
        multiprocessing.set_start_method('spawn')
    except RuntimeError:
        pass  # Start method already set, so we ignore the error

    manager = multiprocessing.Manager()
    exception = manager.list([])  # This allows sharing across processes
    chat_input = manager.list([])
    

    thread = Thread(target=create_python_from_instruction, args=([current_running_scripts, prompt_history, chat_input]), daemon=True) # background thread
    thread.start()

    correction_thread = Thread(target=scene_correction_python, args=([current_running_scripts, prompt_history, arena_python_queue, exception]), daemon=True)
    correction_thread.start()

    # Initialize the queue
    current_process = None

    #create a process to get strings from chat
    p = multiprocessing.Process(target=run_code, args=(get_chat_code, exception, chat_input))
    p.start()

    while True:
        try:
            if not arena_python_queue.empty():
                pythoncode = arena_python_queue.get()

                # Terminate current process if running
                if current_process is not None and current_process.is_alive():
                    current_running_scripts.pop()
                    current_process.terminate()
                    current_process.join()

                # Start new process with new code
                current_running_scripts.append(pythoncode)
                current_process = multiprocessing.Process(target=run_code, args=(pythoncode, exception, chat_input))
                current_process.start()

            time.sleep(0.1)

        except KeyboardInterrupt:
            print("Exiting program...")
            time_end = time.time()
            curr_prompt = prompt_history[-1]
            if current_process is not None and current_process.is_alive():
                current_process.terminate()
                current_process.join()
            break


# #needs to be edited to handle more than one script at a time
# current_running_scripts = []
# prompt_history = []

# time_start = []
# num_LLM_calls = [0]

# chat_input = []
# exception = []

# get_chat_code = f"""
# import arena


# def chat_handler(_scene, chatmsg, _rawmsg):
#     print(f"Chat Message:{{chatmsg.text.strip()}}")

# scene = arena.Scene(host="arenaxr.org", scene="{ARENA_SCENE_NAME}", on_chat_callback=chat_handler)

# scene.run_tasks()
# """

# class LiveOutput:
#     """A wrapper around sys.stdout to print and capture output at the same time."""
#     def __init__(self):
#         self.output = []  # Stores all captured output
#         self.exception = ""  # Stores any exception message

#     def write(self, message):
#         #check if message has stderr
#         sys.__stdout__.write(message)  # Print to actual stdout in real-time
#         self.output.append(message)    # Store the message
#         if "Something went wrong!" in message:
#             # sys.__stdout__.write("Error: " + message)
#             exception.append(message)
#             sys.__stdout__.write("Error: " + str(exception))
#         if "Chat Message:" in message:
#             chat_input.append(message.split(":")[1])
#             print("Chat Message!!!!!!!!!!: " + chat_input[-1])

#     def flush(self):
#         sys.__stdout__.flush()  # Ensure real-time output

# def run_code(python_code,exception):
#     #FOR TESTING ONLY
#     # with open("test_cases/Open-loop-RAG-scripts/output.py", "w") as f:
#     #     #delete existing content
#     #     f.truncate(0)
#     #     f.write(python_code)
#     live_output = LiveOutput()
#     ##reset exception
#     exception[:] = []

#     sys.stdout = live_output   # Redirect stdout to our custom class

#     try:
#         exec(python_code, globals())  # Run the user code
#     except Exception:
#         exception.append(traceback.format_exc())  # Capture full traceback of the error
#         print(exception)  # Ensure error is printed in real-time

#     # Restore original stdout
#     sys.stdout = sys.__stdout__
    

#     return "".join(live_output.output), exception  # Return captured output and any errors


# if __name__ == '__main__':
#     manager = multiprocessing.Manager()
#     exception = manager.list([])  # This allows sharing across processes
#     chat_input = manager.list([])



#     thread = Thread(target=create_python_from_instruction, args=([current_running_scripts, prompt_history, chat_input, time_start, num_LLM_calls]), daemon=True) # background thread
#     thread.start()

#     correction_thread = Thread(target=scene_correction_python, args=([current_running_scripts, prompt_history, arena_python_queue, exception, num_LLM_calls]), daemon=True)
#     correction_thread.start()


#     # Set start method only if not already set
#     try:
#         multiprocessing.set_start_method('spawn')
#     except RuntimeError:
#         pass  # Start method already set, so we ignore the error

#     # Initialize the queue
#     current_process = None

#     #create a process to get strings from chat
#     p = multiprocessing.Process(target=run_code, args=(get_chat_code,exception))
#     p.start()

#     while True:
#         try:
#             if not arena_python_queue.empty():
#                 pythoncode = arena_python_queue.get()
#                 # print(f"New code received:\n{pythoncode}")

#                 # Terminate current process if running
#                 if current_process is not None and current_process.is_alive():
#                     # print("Terminating current process...")
#                     current_running_scripts.pop()
#                     current_process.terminate()
#                     current_process.join()
#                     # print("Terminated.")

#                 # Start new process with new code
#                 current_running_scripts.append(pythoncode)
#                 current_process = multiprocessing.Process(target=run_code, args=(pythoncode,exception))
#                 current_process.start()

#             time.sleep(0.1)

#         except KeyboardInterrupt:
#             print("Exiting program...")
#             if current_process is not None and current_process.is_alive():
#                 current_process.terminate()
#                 current_process.join()
#             break
