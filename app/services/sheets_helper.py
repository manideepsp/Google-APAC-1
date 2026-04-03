import gspread
from google.oauth2.service_account import Credentials


def get_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_file(
        "keys/credentials.json",
        scopes=scopes
    )

    return gspread.authorize(creds)


def get_sheet(sheet_name="YouTube Agent Dashboard"):
    client = get_client()
    return client.open(sheet_name)