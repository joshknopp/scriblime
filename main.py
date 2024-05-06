import os.path
import json
import time
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import googleapiclient.errors
import os
from dotenv import load_dotenv
from datetime import datetime
import mimetypes

# Load environment variables from .env file
load_dotenv()

# Scopes required for Drive and Sheets API
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']

# Google Drive folder and file details
FOLDER_NAME = 'scriblime'
LOG_FILE_NAME = 'scriblime.log'
SHEET_NAME = 'Sheet1'

TOKEN_FILE = 'config/token.json'
CREDENTIALS_FILE = 'config/credentials.json'

def authenticate():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return creds

folder_id_cache = {}

def get_folder_id(folder_name):
    # Check if the folder ID is already cached
    if folder_name in folder_id_cache:
        return folder_id_cache[folder_name]

    # Folder ID not found in cache, make API call
    creds = authenticate()
    drive_service = build('drive', 'v3', credentials=creds)
    results = drive_service.files().list(q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'",
                                   spaces='drive',
                                   fields='files(id)').execute()
    items = results.get('files', [])
    if not items:
        # Folder not found, create it
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = drive_service.files().create(body=folder_metadata,
                                        fields='id').execute()
        folder_id = folder.get('id')
        # Cache the folder ID
        folder_id_cache[folder_name] = folder_id
        return folder_id
    else:
        folder_id = items[0]['id']
        # Cache the folder ID
        folder_id_cache[folder_name] = folder_id
        return folder_id


spreadsheet_id_cache = {}

def create_spreadsheet(service, folder_id):
    # Check if the spreadsheet ID is already cached
    if folder_id in spreadsheet_id_cache:
        return spreadsheet_id_cache[folder_id]

    # Spreadsheet ID not found in cache, make API call
    creds = authenticate()
    drive_service = build('drive', 'v3', credentials=creds)
    results = drive_service.files().list(q=f"name='{LOG_FILE_NAME}' and '{folder_id}' in parents and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
                                   spaces='drive',
                                   fields='files(id)').execute()
    items = results.get('files', [])
    if not items:
        # Create the spreadsheet in the specified folder
        file_metadata = {
            'name': LOG_FILE_NAME,
            'parents': [folder_id],
            'mimeType': 'application/vnd.google-apps.spreadsheet'
        }
        spreadsheet = drive_service.files().create(body=file_metadata,
                                              fields='id').execute()
        spreadsheet_id = spreadsheet.get('id')

        # Write headers to the spreadsheet
        values = [
            ["File ID", "File Name", "Acknowledged", "Processing", "Completed", "Results URL"]
        ]
        body = {
            'values': values
        }
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range='Sheet1',
            valueInputOption='RAW',
            body=body
        ).execute()
        
        # Cache the spreadsheet ID
        spreadsheet_id_cache[folder_id] = spreadsheet_id
        return spreadsheet_id
    else:
        spreadsheet_id = items[0]['id']
        # Cache the spreadsheet ID
        spreadsheet_id_cache[folder_id] = spreadsheet_id
        return spreadsheet_id

def update_sheet(row_data):
    creds = authenticate()
    service = build('sheets', 'v4', credentials=creds)

    # Get the folder ID
    folder_id = get_folder_id(FOLDER_NAME)

    # Create or get the spreadsheet ID
    spreadsheet_id = create_spreadsheet(service, folder_id)

    # Use the Sheets API to update the spreadsheet
    sheet = service.spreadsheets()

    # Get values from the spreadsheet
    result = sheet.values().get(spreadsheetId=spreadsheet_id,
                                 range=SHEET_NAME).execute()
    values = result.get('values', [])

    # Check if file_id exists in the spreadsheet
    file_id_exists = False
    for i, row in enumerate(values):
        if row and row[0] == row_data[0]:  # Assuming file_id is in the first column
            # Update the existing row with new data
            values[i] = row_data
            file_id_exists = True
            break

    # If file_id does not exist, add a new row with row_data
    if not file_id_exists:
        values.append(row_data)

    body = {
        'values': values
    }

    # Write updated values to the spreadsheet
    result = sheet.values().update(
        spreadsheetId=spreadsheet_id,
        range=SHEET_NAME,
        valueInputOption='RAW',
        body=body
    ).execute()
    print('Row updated/added:', result)

def process_notification(notification):
    file_id = notification['fileId']
    file_name = notification['fileName']
    
    # Capture timestamps for each phase
    acknowledged_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    processing_time = None  # Will be updated later
    completed_time = None  # Will be updated later
    url = None

    # Acknowledge the file in the spreadsheet - TODO will probably scrap this in later dev
    row_data = [file_id, file_name, acknowledged_time, processing_time, completed_time, url]
    update_sheet(row_data)
    
    # Check if the file is a sound or video file
    mime_type, _ = mimetypes.guess_type(file_name)
    if mime_type and mime_type.startswith(('audio/', 'video/')):
        # Show as processing the file in the spreadsheet
        processing_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        row_data = [file_id, file_name, acknowledged_time, processing_time, completed_time, url]
        update_sheet(row_data)
        
        # Check if the document already exists
        creds = authenticate()
        drive_service = build('drive', 'v3', credentials=creds)
        folder_id = get_folder_id(FOLDER_NAME)
        query = f"name='{file_name}.docx' and '{folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
        results = drive_service.files().list(q=query, fields='files(id)').execute()
        existing_files = results.get('files', [])
        
        if not existing_files:
            # Create a new Google Doc
            file_metadata = {
                'name': f"{file_name}.docx",
                'parents': [folder_id],
                'mimeType': 'application/vnd.google-apps.document'
            }
            new_doc = drive_service.files().create(body=file_metadata).execute()
            
            # Write the current datetime as a string to the body of the new document
            current_datetime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            service = build('docs', 'v1', credentials=creds)
            service.documents().batchUpdate(documentId=new_doc['id'], body={
                'requests': [
                    {
                        'insertText': {
                            'location': {'index': 1},
                            'text': current_datetime_str
                        }
                    }
                ]
            }).execute()

            # Show as completed the file in the spreadsheet
            completed_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            row_data = [file_id, file_name, acknowledged_time, processing_time, completed_time, url]
            update_sheet(row_data)
        else:
            print(f"Document {file_name}.docx already exists. Skipping creation.")
    else:
        print(f"Ignoring file {file_name}: Not a sound or video file")
        # Show as ignored the file in the spreadsheet - TODO will probably scrap this in later dev
        url = "Skipped - no audio"
        row_data = [file_id, file_name, acknowledged_time, processing_time, completed_time, url]
        update_sheet(row_data)


def get_folder_id_by_name(service, folder_name):
    # Search for the folder by name
    results = service.files().list(q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                                   spaces='drive',
                                   fields='files(id)').execute()
    items = results.get('files', [])
    if not items:
        raise ValueError(f"Folder '{folder_name}' not found.")
    else:
        return items[0]['id']

def get_date_time_string():
    current_date_time = datetime.now()
    current_date_time_str = current_date_time.strftime("%Y-%m-%d %H:%M:%S")
    return current_date_time_str

def watch_folder():
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)
    
    # Get the folder ID by name
    folder_id = get_folder_id_by_name(service, FOLDER_NAME)
    
    # Track the files that have already been processed
    # TODO Populate this with any fileIds that exist in spreadsheet with non-empty Completed date
    processed_files = set()
    
    # TODO Do we need a way to cleanly terminate?
    while True:
        print(f"{get_date_time_string()} Checking for new files")
        # Get the list of files in the folder
        results = service.files().list(q=f"'{folder_id}' in parents",
                                        fields='files(id, name, trashed)').execute()
        files = results.get('files', [])
        
        for file in files:
            file_id = file['id']
            file_name = file['name']
            is_trashed = file.get('trashed', False)
            
            # Check if the file has already been processed or if it's trashed
            if file_id not in processed_files and not is_trashed:
                print(f"New file detected: {file_name}")
                # Invoke the process_notification method
                process_notification({'fileId': file_id, 'fileName': file_name})
                # Add the file to the processed set
                processed_files.add(file_id)
        
        # Wait for a while before checking again
        print(f"{get_date_time_string()} Sleeping for a minute")
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    watch_folder()
