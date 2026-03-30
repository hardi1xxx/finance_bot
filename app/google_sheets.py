import json
import os
import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


class GoogleSheetsManager:
    def __init__(self):
        self.spreadsheet_id = os.getenv('SPREADSHEET_ID')
        self.sheet_name = os.getenv('SHEET_NAME', 'Pengeluaran+pemasukan')
        
        # Railway / Cloud Run
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        scopes = ['https://www.googleapis.com/auth/spreadsheets']

        if creds_json:
            creds_info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        else:
            creds_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH')
            creds = Credentials.from_service_account_file(creds_path, scopes=scopes)

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
        
        body = {'values': values}
        range_name = f"{self.sheet_name}!A:F"
        
        self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()

    def get_summary(self, days: int = 30) -> dict:
        range_name = f"{self.sheet_name}!A:F"
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=range_name
        ).execute()
        
        rows = result.get('values', [])
        if not rows:
            return {}
        
        df = pd.DataFrame(rows[1:], columns=rows[0])
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        
        total_income = df[df['type'] == 'Pemasukan']['amount'].sum()
        total_expense = df[df['type'] == 'Pengeluaran']['amount'].sum()
        balance = total_income - total_expense
        
        return {
            'total_income': float(total_income or 0),
            'total_expense': float(total_expense or 0),
            'balance': float(balance or 0),
            'total_transactions': len(df)
        }