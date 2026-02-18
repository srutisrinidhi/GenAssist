import requests
import os

def search_and_download_gltf(query, api_token, download_path, max_results=5):
    """
    Searches for downloadable models with .gltf availability and downloads the first matching model.

    Parameters:
    - query: Search query string.
    - api_token: Your Sketchfab API token.
    - download_path: Directory where the model will be saved.
    - max_results: Maximum number of results to consider (default: 5).

    Returns:
    - Path to the downloaded model ZIP file or None if no model is found.
    """
    # Step 1: Search for models
    search_url = 'https://api.sketchfab.com/v3/search'
    headers = {'Authorization': f'Token {api_token}'}
    search_params = {
        'q': query,
        'type': 'models',
        'downloadable': True,
        'page': 1,
        'per_page': 10
    }
    search_response = requests.get(search_url, headers=headers, params=search_params)
    search_response.raise_for_status()
    results = search_response.json().get('results', [])
    print(results)

    # Step 2: Filter for glTF availability
    for model in results[:max_results]:
        model_uid = model['uid']
        model_title = model['name']
        download_url = f'https://api.sketchfab.com/v3/models/{model_uid}/download'
        print(download_url)
        download_response = requests.get(download_url, headers=headers)
        
        if download_response.status_code == 200 and 'gltf' in download_response.json():
            # Step 3: Download the model
            gltf_info = download_response.json()['gltf']
            model_download_url = gltf_info['url']
            model_response = requests.get(model_download_url)
            model_response.raise_for_status()

            # Save the model as a ZIP file
            os.makedirs(download_path, exist_ok=True)
            model_filename = os.path.join(download_path, f'{model_uid}.zip')
            with open(model_filename, 'wb') as model_file:
                model_file.write(model_response.content)
            print(f'Model downloaded to {model_filename}')
            return model_filename


    print('No downloadable glTF models found for the query.')
    return None


