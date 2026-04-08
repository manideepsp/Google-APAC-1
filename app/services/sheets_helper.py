import os

import gspread
import google.auth
from google.oauth2.service_account import Credentials


def get_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    credential_file = str(os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")).strip() or "keys/credentials.json"

    if os.path.isfile(credential_file):
        creds = Credentials.from_service_account_file(
            credential_file,
            scopes=scopes,
        )
    else:
        creds, _ = google.auth.default(scopes=scopes)

    return gspread.authorize(creds)


def get_sheet(sheet_name="YouTube Agent Dashboard"):
    client = get_client()
    return client.open(sheet_name)