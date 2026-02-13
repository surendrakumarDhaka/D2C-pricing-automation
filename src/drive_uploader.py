import os
import mimetypes

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

def upload_with_versioning(
    file_path: str,
    credentials_path: str,
    parent_folder_id: str,
) -> str:
    """
    Uploads a file to a specific folder.
    If a file with the same name exists, renames the old one with '_old' prefix.
    """
    creds = Credentials.from_service_account_file(credentials_path)
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    
    file_name = os.path.basename(file_path)
    
    # Check for existing file
    query = f"name = '{file_name}' and '{parent_folder_id}' in parents and trashed = false"
    try:
        resp = service.files().list(
            q=query,
            fields="files(id, name)",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True
        ).execute()
        files = resp.get('files', [])
        
        if files:
            existing_file = files[0]
            existing_id = existing_file['id']
            new_name = f"_old_{file_name}"
            
            # Check if _old file exists and delete it if so (to avoid name collision)
            old_query = f"name = '{new_name}' and '{parent_folder_id}' in parents and trashed = false"
            old_resp = service.files().list(
                q=old_query,
                fields="files(id)",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True
            ).execute()
            old_files = old_resp.get('files', [])
            for old_f in old_files:
                try:
                    service.files().delete(fileId=old_f['id'], supportsAllDrives=True).execute()
                    print(f"Deleted existing old version: {new_name}")
                except HttpError:
                    pass

            # Rename current existing file
            body = {'name': new_name}
            service.files().update(
                fileId=existing_id,
                body=body,
                supportsAllDrives=True
            ).execute()
            print(f"Renamed existing file to: {new_name}")
            
    except HttpError as e:
        print(f"Error checking/renaming existing file: {e}")

    # Upload new file
    file_metadata = {
        'name': file_name,
        'parents': [parent_folder_id]
    }
    
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = 'application/octet-stream'
        
    media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
    
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink',
        supportsAllDrives=True
    ).execute()
    
    print(f"Uploaded: {file_name}")
    return file.get('webViewLink')


def get_or_create_folder(
    credentials_path: str,
    parent_folder_id: str,
    folder_name: str
) -> str:
    """
    Finds or creates a folder with the given name under parent_folder_id.
    """
    creds = Credentials.from_service_account_file(credentials_path)
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