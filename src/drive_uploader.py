import os
import io
import re
import json
import mimetypes
import datetime
import time
import socket

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

from src.logger import get_logger

logger = get_logger(__name__)


def extract_file_id_from_link(link: str) -> str:
    """
    Extracts a Google Drive file ID from various link formats:
      - https://drive.google.com/file/d/{ID}/view...
      - https://drive.google.com/open?id={ID}
      - https://docs.google.com/spreadsheets/d/{ID}/edit...
      - Raw file ID string
    """
    link = link.strip()
    patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)',
        r'/spreadsheets/d/([a-zA-Z0-9_-]+)',
        r'/document/d/([a-zA-Z0-9_-]+)',
        r'[?&]id=([a-zA-Z0-9_-]+)',
    ]
    for pattern in patterns:
        m = re.search(pattern, link)
        if m:
            return m.group(1)
    if re.match(r'^[a-zA-Z0-9_-]{10,}$', link):
        return link
    raise ValueError(f"Could not extract file ID from: {link}")


def get_service_account_email(credentials_path: str) -> str:
    """Returns the service account email from the credentials JSON file."""
    try:
        with open(credentials_path, "r") as f:
            creds_data = json.load(f)
        return creds_data.get("client_email", "")
    except Exception as e:
        logger.warning("Could not read service account email: %s", e)
        return ""


def check_drive_access(file_id: str, credentials_path: str) -> dict:
    """
    Checks if the service account can access a Drive file.
    Uses supportsAllDrives for Shared Drive compatibility.
    Returns dict: { "accessible": bool, "file_name": str|None, "mime_type": str|None, "error": str|None }
    """
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    sa_email = get_service_account_email(credentials_path)

    logger.info("Checking Drive access for file_id=%s, SA=%s", file_id, sa_email)

    try:
        meta = service.files().get(
            fileId=file_id,
            fields='id, name, mimeType, driveId',
            supportsAllDrives=True
        ).execute()
        drive_id = meta.get('driveId')
        logger.info("Drive access OK: file_id=%s, name=%s, mime=%s, driveId=%s",
                     file_id, meta.get('name'), meta.get('mimeType'), drive_id)
        return {
            "accessible": True,
            "file_name": meta.get("name"),
            "mime_type": meta.get("mimeType"),
            "error": None
        }
    except HttpError as e:
        status = e.resp.status
        logger.warning("files.get failed for file_id=%s (status=%s): %s", file_id, status, e)

        if status == 404:
            return {
                "accessible": False,
                "file_name": None,
                "mime_type": None,
                "error": (
                    f"Please give the file access to below email address."
                )
            }
        elif status == 403:
            return {
                "accessible": False,
                "file_name": None,
                "mime_type": None,
                "error": (
                    f"Please give the file access to below email address."
                )
            }
        logger.error("Unexpected Drive API error for file_id=%s: %s", file_id, e, exc_info=True)
        raise


def download_drive_file(file_id: str, credentials_path: str, dest_path: str) -> str:
    """
    Downloads a file from Google Drive to dest_path.
    For Google Sheets, exports as .xlsx.
    Returns the final local file path.
    """
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)

    meta = service.files().get(
        fileId=file_id,
        fields='id, name, mimeType',
        supportsAllDrives=True
    ).execute()

    file_name = meta.get('name', 'download')
    mime = meta.get('mimeType', '')
    logger.info("Downloading file: id=%s, name=%s, mime=%s", file_id, file_name, mime)

    buf = io.BytesIO()

    if mime == 'application/vnd.google-apps.spreadsheet':
        request = service.files().export_media(
            fileId=file_id,
            mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        if not file_name.endswith('.xlsx'):
            file_name = os.path.splitext(file_name)[0] + '.xlsx'
    else:
        request = service.files().get_media(fileId=file_id)

    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            logger.debug("Download progress: %d%%", int(status.progress() * 100))

    final_path = os.path.join(dest_path, os.path.basename(file_name))
    with open(final_path, 'wb') as f:
        f.write(buf.getvalue())

    logger.info("Downloaded to: %s (%d bytes)", final_path, buf.tell())
    return final_path


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

    base_name = os.path.basename(file_path)
    name_stem, ext = os.path.splitext(base_name)
    current_date = datetime.datetime.now().strftime("%d_%m_%Y")
    new_filename = f"{name_stem}_{current_date}{ext}"

    logger.info("Uploading file: %s -> %s (folder=%s)", base_name, new_filename, parent_folder_id)

    # Check for existing file with same dated name
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
            logger.info("Found %d existing file(s) with name '%s', deleting...", len(files), new_filename)
            for existing_file in files:
                existing_id = existing_file['id']
                try:
                    service.files().delete(fileId=existing_id, supportsAllDrives=True).execute()
                    logger.info("Deleted existing file: %s (id=%s)", new_filename, existing_id)
                except HttpError as e:
                    logger.warning("Error deleting file %s (id=%s): %s", new_filename, existing_id, e)
        else:
            logger.debug("No existing file named '%s' found", new_filename)

    except HttpError as e:
        logger.warning("Error checking existing files: %s", e)

    # Upload with retry
    file_metadata = {
        'name': new_filename,
        'parents': [parent_folder_id]
    }

    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = 'application/octet-stream'

    file_size = os.path.getsize(file_path)
    logger.info("Starting upload: %s (size=%d bytes, mime=%s)", new_filename, file_size, mime_type)

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

            link = file.get('webViewLink')
            logger.info("Upload successful: %s (id=%s, link=%s) on attempt %d", new_filename, file.get('id'), link, attempt + 1)
            return link

        except (HttpError, socket.timeout, Exception) as e:
            last_exception = e
            wait_time = (2 ** attempt) * 2

            is_transient = False
            if isinstance(e, HttpError):
                if e.resp.status in [408, 429, 500, 502, 503, 504]:
                    is_transient = True
                logger.warning("Upload HttpError (status=%s): %s", e.resp.status, e)
            elif isinstance(e, socket.timeout):
                is_transient = True
                logger.warning("Upload socket timeout: %s", e)
            else:
                is_transient = True
                logger.warning("Upload generic error: %s", e)

            if is_transient and attempt < max_retries - 1:
                logger.info("Retry %d/%d for '%s' in %ds...", attempt + 1, max_retries, new_filename, wait_time)
                time.sleep(wait_time)
            else:
                logger.error("Upload FAILED for '%s' after %d attempt(s): %s", new_filename, attempt + 1, e)
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
    logger.info("Looking for folder '%s' under parent=%s", folder_name, parent_folder_id)

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
        folder_id = files[0]['id']
        logger.info("Found existing folder '%s' (id=%s)", folder_name, folder_id)
        return folder_id

    # Create folder
    metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_folder_id]
    }
    folder = service.files().create(body=metadata, fields='id', supportsAllDrives=True).execute()
    folder_id = folder['id']
    logger.info("Created new folder '%s' (id=%s)", folder_name, folder_id)
    return folder_id
