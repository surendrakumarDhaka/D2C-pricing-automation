import os
import mimetypes
import datetime
import time
import socket

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

def upload_with_versioning(
    file_path: str,
    credentials_path: str,
    parent_folder_id: str,
    max_retries: int = 5
) -> str:
    """
    Uploads a file to a specific folder.
    Renames the file to include the current date (dd_mm_yyyy).
    If a file with the same name exists, deletes the previous one before uploading.
    Includes exponential backoff retry for uploads.
    """
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    
    # Construct new filename with date
    base_name = os.path.basename(file_path)
    name_stem, ext = os.path.splitext(base_name)
    current_date = datetime.datetime.now().strftime("%d_%m_%Y")
    
    new_filename = f"{name_stem}_{current_date}{ext}"
    
    # Check for existing file with NEW name
    query = f"name = '{new_filename}' and '{parent_folder_id}' in parents and trashed = false"
    try:
        resp = service.files().list(
            q=query,
            fields="files(id, name)",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True
        ).execute()
        files = resp.get('files', [])
        
        if files:
            for existing_file in files:
                existing_id = existing_file['id']
                # Delete existing file
                try:
                    service.files().delete(fileId=existing_id, supportsAllDrives=True).execute()
                    print(f"Deleted existing file: {new_filename}")
                except HttpError as e:
                    print(f"Error deleting file {new_filename}: {e}")
            
    except HttpError as e:
        print(f"Error checking existing file: {e}")

    # Upload new file with retry logic
    file_metadata = {
        'name': new_filename,
        'parents': [parent_folder_id]
    }
    
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = 'application/octet-stream'

    last_exception = None
    
    for attempt in range(max_retries):
        try:
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink',
                supportsAllDrives=True
            ).execute()
            
            print(f"Uploaded: {new_filename}")
            return file.get('webViewLink')
            
        except (HttpError, socket.timeout, Exception) as e:
            last_exception = e
            wait_time = (2 ** attempt) * 2
            
            # Check for specific HttpErrors if possible
            is_transient = False
            if isinstance(e, HttpError):
                if e.resp.status in [408, 429, 500, 502, 503, 504]:
                    is_transient = True
            elif isinstance(e, socket.timeout):
                 is_transient = True
            else:
                 # Treat generic exceptions (like "write operation timed out") as transient for upload
                 is_transient = True
                 
            if is_transient and attempt < max_retries - 1:
                print(f"Upload failed for {new_filename} (Attempt {attempt + 1}/{max_retries}). Error: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"Upload failed for {new_filename} after {attempt + 1} attempts.")
                raise e

    raise last_exception if last_exception else Exception("Upload failed")


def get_or_create_folder(
    credentials_path: str,
    parent_folder_id: str,
    folder_name: str
) -> str:
    """
    Finds or creates a folder with the given name under parent_folder_id.
    """
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    
    query = (
        f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and "
        f"'{parent_folder_id}' in parents and trashed = false"
    )
    
    resp = service.files().list(
        q=query,
        fields="files(id, name)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True
    ).execute()
    
    files = resp.get('files', [])
    if files:
        return files[0]['id']
        
    # Create folder
    metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_folder_id]
    }
    folder = service.files().create(body=metadata, fields='id', supportsAllDrives=True).execute()
    return folder['id']