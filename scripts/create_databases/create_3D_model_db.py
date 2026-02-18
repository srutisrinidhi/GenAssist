import os
import sys
import logging
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
import requests
from bs4 import BeautifulSoup
import urllib.parse
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from config import OPENAI_API_KEY as API_KEY, ARENA_STORE_URL

embeddings_model = OpenAIEmbeddings(openai_api_key=API_KEY, model="text-embedding-ada-002")


def scrape_files_from_directory(url):
    # Request the page
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Failed to retrieve the page. Status code: {response.status_code}")
        return {}

    #parse the page
    soup = BeautifulSoup(response.content, 'html.parser')

    files = {}

    #find all files not folders
    for link in soup.find_all('a', href=True):
        href = link.get('href')

        if href in ["../", "."]:
            continue

        #if it is a folder
        if href.endswith("/"):
            folder_url = urllib.parse.urljoin(url, href)
            folder_response = requests.get(folder_url)
            folder_soup = BeautifulSoup(folder_response.content, 'html.parser')
            for folder_link in folder_soup.find_all('a', href=True):
                folder_href = folder_link.get('href')
                if folder_href in ["..", "."]:
                    continue
                if folder_href.endswith(".gltf") or folder_href.endswith(".glb"):
                    model_name = href.split("/")[0]
                    if "Cube" in model_name:
                        continue
                    files[model_name] = urllib.parse.urljoin(folder_url, folder_href)
            continue

        if not href.endswith(".mtl") and not href.endswith(".bin"):
            model_name = link.text.split(".")[0]
            if "Cube" in model_name:
                continue
            files[model_name] = urllib.parse.urljoin(url, href)
    return files


def create_3D_model_db(models, path):
    texts = list(models.keys())
    metadatas = [{"url": url} for url in models.values()]
    ids = list(models.keys())
    Chroma.from_texts(texts, embedding=embeddings_model, metadatas=metadatas, ids=ids,
                      persist_directory=path, collection_name="model_embeddings")
    print("Embeddings stored in ChromaDB.")


def load_model_db(path):
    return Chroma(persist_directory=path, embedding_function=embeddings_model,
                  collection_name="model_embeddings")


def find_closest_model(prompt, db):
    results = db.similarity_search_with_score(prompt, k=4)
    models = []
    for doc, score in results:
        if score < 0.4:
            models.append(doc.metadata["url"])
    return models


if __name__ == "__main__":
    models = scrape_files_from_directory(ARENA_STORE_URL)
    path = "model_db"
    create_3D_model_db(models, path)
    db = load_model_db(path)
    # Example usage
    prompt = "create a vase at 0 0 0"
    closest_model_url = find_closest_model(prompt, db)
    print("Best match URL:", closest_model_url)
