import os.path
import json
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import requests

# Path to your credentials JSON file
credentials_file = '.env/credentials.json'

# Scopes required for Drive and Sheets API
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']

# Google Sheets ID and range
SPREADSHEET_ID = 'your_spreadsheet_id'
SHEET_NAME = 'Sheet1'

TOKEN_FILE = '.env/token.json'
CREDENTIALS_FILE = '.env/credentials.json'

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

def update_sheet(row_data):
    creds = authenticate()
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    
    values = [row_data]
    body = {
        'values': values
    }
    
    result = sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=SHEET_NAME,
        valueInputOption='RAW',
        body=body
    ).execute()
    print('Row added:', result)

def process_notification(notification):
    file_id = notification['fileId']
    # Check if the file is an audio file (implement your logic here)
    # For example, you can check the file's MIME type
    # If it's an audio file, acknowledge it in the spreadsheet
    row_data = [file_id, 'Acknowledged', '', '']
    update_sheet(row_data)
    
    # Invoke AssemblyAI for transcription
    # (implement this part based on AssemblyAI's API documentation)
    # For example:
    # transcription_result = invoke_assemblyai(file_id)
    # Update the spreadsheet to indicate processing
    row_data[2] = 'Processing'
    update_sheet(row_data)
    
    # Poll AssemblyAI for transcription status
    # (implement this part based on AssemblyAI's API documentation)
    # For example:
    # status = poll_assemblyai_status(transcription_result)
    # Once transcription is complete, update the spreadsheet again
    row_data[2] = 'Completed'
    row_data[3] = 'Transcription Result URL'  # Update with the actual URL
    update_sheet(row_data)
