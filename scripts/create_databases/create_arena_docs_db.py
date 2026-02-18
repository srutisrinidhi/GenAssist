# load required library
import logging
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
import chromadb
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveJsonSplitter
from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from openai  import OpenAI
from langchain_core.documents import Document
import os
import json
from tqdm import tqdm
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from config import OPENAI_API_KEY as API_KEY


#file paths
json_folder_path = r'./arena-web-core/build/schemas'
python_api_path = r"./arena-docs/content/python-api"
json_schemas_path = r"./arena-schemas/schemas"
persistent_directory_json = r"./arena_docs_db_ada_json"
persistent_directory_python = r"./arena_docs_db_ada_python"
persistent_directory_json_gpt = r"./arena_docs_db_ada_json_gpt"


# Load the embedding and LLM model
embeddings_model = OpenAIEmbeddings(openai_api_key = API_KEY, model="text-embedding-ada-002")
llm = ChatOpenAI(model_name = "gpt-4o", max_tokens = 4096, openai_api_key = API_KEY)
client = OpenAI(api_key=API_KEY)
# splitter = RecursiveJsonSplitter(max_chunk_size=600)

#load markdown


def load_files(file):
    with open(file, 'r') as file:
        text = file.read()


    # Replace new lines and double spaces (keep single spaces and remove longer ones)
    text = text.replace('\n', '')
    text = text.replace('  ', ' ')
    return text


def read_files(python_docs):
    arena_docs = []


    [dir_path, sub_dirs, sub_files] = next(os.walk(python_docs))
    for dir in sub_dirs:
        if dir in ["examples"]:

            [dir_path, sub_dirs, sub_files] = next(os.walk(python_docs + "/" + dir))
            for sub_file in sub_files:
                arena_docs.append({"content": load_files(dir_path + "/" + sub_file), "metadata": {'path':dir_path + "/" + sub_file}})
            for sub_dir in sub_dirs:
                print(sub_dir)
                if sub_dir in ["legacy", "demos"]:
                    continue
                [sub_dir_path, sub_sub_dirs, sub_sub_files] = next(os.walk(dir_path + "/"+ sub_dir ))
                for sub_sub_file in sub_sub_files:
                    arena_docs.append({"content": load_files(sub_dir_path + "/" + sub_sub_file), "metadata": {'path':sub_dir_path + "/" + sub_sub_file}} )

    return arena_docs


def get_file_splits(directory):
    arena_docs = read_files(directory)

    splits = [
            Document(page_content=chunk["content"], metadata=chunk["metadata"])
            for chunk in arena_docs
        ]
    return splits


def create_database(persistent_directory, files_directory):
    splits = get_file_splits(files_directory)

    # For Debugging only
    write_db_to_file(splits)

    if not os.path.exists(persistent_directory):
        os.makedirs(persistent_directory)


    # Store data into database
    db = Chroma.from_documents(splits, embedding=embeddings_model, persist_directory=persistent_directory,
                               client_settings=chromadb.Settings(anonymized_telemetry=False))

    return db


def write_db_to_file(splits):

    csv_file = "output.txt"

    # Write data to CSV file
    with open(csv_file, mode='w', newline='\n', encoding='utf-8') as file:
        # Write the data rows
        for row in splits:
            file.writelines(json.dumps(row.page_content, indent=4)+ '\n\n')


if __name__ == "__main__":
    persistent_directory_python = r"./arena_python_docs"
    python_docs = r"./arena-py"
    create_database(persistent_directory_python, python_docs)
    print("Created Database!")
