import re
from django.conf import settings
from django.core.cache import cache
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

import os
import json

SERVICE_ACCOUNT_FILE = settings.BASE_DIR / 'service_account.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def get_drive_service():
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        try:
            info = json.loads(sa_json)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception as e:
            raise ValueError(f"Error parsing GOOGLE_SERVICE_ACCOUNT_JSON in GDrive: {str(e)}")
    else:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            raise FileNotFoundError(f"Service account file not found at {SERVICE_ACCOUNT_FILE} and GOOGLE_SERVICE_ACCOUNT_JSON env var is empty.")
        creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_FILE), scopes=SCOPES)
    
    return build('drive', 'v3', credentials=creds)

def extract_folder_id(url: str) -> str:
    """
    Extracts Google Drive folder ID from a URL using regex.
    """
    match = re.search(r"[-\w]{25,}", url)
    if match:
        return match.group(0)
    return None

def fetch_folder_contents(url: str) -> list:
    """
    Fetches the contents of a Google Drive folder and caches it for 5 minutes.
    """
    folder_id = extract_folder_id(url)
    if not folder_id:
        raise ValueError("Invalid Google Drive Folder URL")

    cache_key = f"gdrive_folder_{folder_id}"
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return cached_data

    service = get_drive_service()
    query = f"'{folder_id}' in parents and trashed = false"
    
    try:
        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType, modifiedTime, size)",
            pageSize=100,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        items = results.get('files', [])
        
        # Cache the result for 5 minutes (300 seconds)
        cache.set(cache_key, items, 300)
        return items
    except Exception as e:
        raise Exception(f"Failed to fetch Drive files: {str(e)}")
