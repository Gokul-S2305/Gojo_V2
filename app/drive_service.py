from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

def get_drive_service(access_token: str):
    """Initialize Google Drive service with access token."""
    creds = Credentials(token=access_token)
    return build('drive', 'v3', credentials=creds)

async def find_or_create_parent_folder(service) -> str:
    """Find or create the 'Gojo Trips' parent folder."""
    query = "name = 'Gojo Trips' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    files = results.get('files', [])
    
    if files:
        return files[0]['id']
    
    # Create folder
    file_metadata = {
        'name': 'Gojo Trips',
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder.get('id')

async def create_trip_folder(service, trip_name: str, parent_id: str) -> str:
    """Create a folder for a specific trip under the parent folder."""
    file_metadata = {
        'name': trip_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder.get('id')

async def upload_file_to_drive(service, file_path: Path, folder_id: str, media_type: str = 'image'):
    """Upload a file to a specific Drive folder."""
    if not file_path.exists():
        logger.error(f"File not found for Drive upload: {file_path}")
        return None
    
    file_metadata = {
        'name': file_path.name,
        'parents': [folder_id]
    }
    
    mimetype = 'image/jpeg' if media_type == 'image' else 'video/mp4'
    media = MediaFileUpload(str(file_path), mimetype=mimetype, resumable=True)
    
    try:
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        logger.error(f"Error uploading to Drive: {e}")
        return None
