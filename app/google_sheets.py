import json
import os
import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


class GoogleSheetsManager:
    def __init__(self):
        self.spreadsheet_id = os.getenv('SPREADSHEET_ID')
        self.sheet_name = os.getenv('SHEET_NAME', 'Sheet1')

        if not self.spreadsheet_id:
            raise ValueError("SPREADSHEET_ID belum diset!")

        scopes = ['https://www.googleapis.com/auth/spreadsheets']

        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')

        if creds_json:
            creds_info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        else:
            raise ValueError("GOOGLE_CREDENTIALS_JSON belum diset!")

        self.service = build('sheets', 'v4', credentials=creds)

    def append_data(self, data: dict):
        values = [[
            data['date'],
            data['type'],
            data['amount'],
            data['description'],
            data['category'],
            data['source']
        ]]

        self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f"{self.sheet_name}!A:F",
            valueInputOption='RAW',
            body={'values': values}
        ).execute()

    def get_summary(self):
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"{self.sheet_name}!A:F"
        ).execute()

        rows = result.get('values', [])

        if len(rows) < 2:
            return dict(total_income=0, total_expense=0, balance=0, total_transactions=0)

        df = pd.DataFrame(rows[1:], columns=rows[0])
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')

        income = df[df['type'] == 'Pemasukan']['amount'].sum()
        expense = df[df['type'] == 'Pengeluaran']['amount'].sum()

        return {
            'total_income': float(income or 0),
            'total_expense': float(expense or 0),
            'balance': float((income - expense) or 0),
            'total_transactions': len(df)
        }