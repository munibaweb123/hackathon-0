#!/usr/bin/env python3
"""
Setup script for Gmail OAuth authentication
"""

import os
import pickle
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Scopes for reading Gmail
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate_gmail():
    """Authenticate with Gmail API and save credentials."""
    creds = None

    # The file token.json stores the user's access and refresh tokens.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Use the credentials file you already have
            if not os.path.exists('client-secret.json'):
                print("Error: client-secret.json not found!")
                print("Please place your Gmail credentials file as 'client-secret.json'")
                return None

            # Run the OAuth flow
            flow = InstalledAppFlow.from_client_secrets_file(
                'client-secret.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds

def test_gmail_connection(creds):
    """Test the Gmail connection."""
    try:
        # Build the Gmail service
        service = build('gmail', 'v1', credentials=creds)

        # Test by getting the user's profile
        profile = service.users().getProfile(userId='me').execute()

        print("✅ Gmail API connection successful!")
        print(f"   Email address: {profile['emailAddress']}")
        print(f"   Messages total: {profile['messagesTotal']}")
        print(f"   Threads total: {profile['threadsTotal']}")

        # Get recent messages
        results = service.users().messages().list(userId='me', maxResults=5).execute()
        messages = results.get('messages', [])

        print(f"\nLatest 5 emails:")
        for msg in messages[:5]:
            msg_detail = service.users().messages().get(userId='me', id=msg['id']).execute()

            # Extract subject and sender
            headers = msg_detail['payload']['headers']
            subject = next((hdr['value'] for hdr in headers if hdr['name'] == 'Subject'), 'No Subject')
            sender = next((hdr['value'] for hdr in headers if hdr['name'] == 'From'), 'Unknown Sender')

            print(f"  • {subject} from {sender}")

        return True

    except Exception as e:
        print(f"❌ Error testing Gmail connection: {e}")
        return False

if __name__ == '__main__':
    print("Setting up Gmail API authentication...")
    print("This will open a browser window for you to authenticate.")

    creds = authenticate_gmail()
    if creds:
        test_gmail_connection(creds)
        print("\n✅ Gmail setup complete! The Silver Tier agent will now use real Gmail API.")
        print("Place the 'token.json' file in the root directory of your project.")
    else:
        print("\n❌ Gmail setup failed.")