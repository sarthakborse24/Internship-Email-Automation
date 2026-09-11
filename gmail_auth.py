import os
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def get_gmail_service():
    """
    Authenticates the user and returns the Gmail service.
    Handles token expiration, refresh errors, and re-authentication automatically.
    """
    creds = None
    token_path = 'token.pickle'
    creds_path = 'credentials.json'

    if os.path.exists(token_path):
        try:
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            print(f"Warning: Could not read {token_path}: {e}")
            creds = None
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Refreshing expired Gmail access token...")
                creds.refresh(Request())
            except Exception as e:
                print(f"Token refresh failed ({e}). Re-authenticating...")
                creds = None

        if not creds or not creds.valid:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(f"'{creds_path}' not found. Please download it from Google Cloud Console.")
            
            print("Launching browser for Gmail OAuth authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        try:
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        except Exception as e:
            print(f"Warning: Failed to save refreshed token to {token_path}: {e}")

    service = build('gmail', 'v1', credentials=creds)
    return service

if __name__ == "__main__":
    print("Testing Gmail authentication...")
    service = get_gmail_service()
    print("Authentication successful!")

