import requests
from lxml import etree
from pathlib import Path
from dotenv import load_dotenv
import os

from check import keybox_check as CheckValid
import hashlib
hash = hashlib.sha256
session = requests.Session()

# Load environment variables from .env file
load_dotenv()

# Access the token from environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN is not set in the .env file")

# Search query
search_query = "<AndroidAttestation>"
search_type = "code"
search_url = f"https://api.github.com/search/code?q={search_query}"

# Headers for the API request
headers = {
	"Authorization": f"token {GITHUB_TOKEN}",
	"Accept": "application/vnd.github.v3+json"
}

# Pagination parameters
per_page = 100

save = Path(__file__).resolve().parent / "keys"

# Function to fetch and print search results
def fetch_and_process_results(page):
    params = {
        "per_page": per_page,
        "page": page
    }
    response = requests.get(search_url, headers=headers, params=params)
    if response.status_code == 200:
        search_results = response.json()
        if 'items' in search_results:
            for item in search_results['items']:
                file_name = item['name']
                # Process only XML files
                if file_name.lower().endswith('.xml'):
                    raw_url = item['html_url'].replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')
                    # Fetch the file content
                    file_content = fetch_file_content(raw_url)
                    # Parse the XML
                    try:
                        root = etree.fromstring(file_content)
                    except etree.XMLSyntaxError:
                        continue
                    # Get the canonical form (C14N)
                    canonical_xml = etree.tostring(root, method="c14n")
                    # Hash the canonical XML
                    hash_value = hashlib.sha256(canonical_xml).hexdigest()
                    file_name_save = save / (hash_value + ".xml")
                    if not file_name_save.exists() and file_content and CheckValid(file_content):
                        print(f"{raw_url} is new")
                        with open( file_name_save, "w") as f:
                            f.write(file_content)
        return len(search_results['items']) > 0  # Return True if there could be more results
    else:
        print(f"Failed to retrieve search results: {response.status_code}")
        return False

# Function to fetch file content
def fetch_file_content(url:str):
    response = session.get(url)
    if response.status_code == 200:
        return response.text
    else:
        print(f"Failed to download {url}")
        exit(1)

# Fetch all pages
page = 1
has_more = True
while has_more:
    has_more = fetch_and_process_results(page)
    page += 1

for file_path in save.glob("*.xml"):
    file_content = file_path.read_text()  # Read file content as a string
    # Run CheckValid to determine if the file is still valid
    if not CheckValid(file_content):
        # Prompt user for deletion
        user_input = input(f"File '{file_path.name}' is no longer valid. Do you want to delete it? (y/n): ")
        if user_input.lower() == 'y':
            try:
                file_path.unlink()  # Delete the file
                print(f"Deleted file: {file_path.name}")
            except OSError as e:
                print(f"Error deleting file {file_path.name}: {e}")
        else:
            print(f"Kept file: {file_path.name}")
