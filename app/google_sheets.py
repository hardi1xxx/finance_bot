import json
import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

  def __init__(self):
        self.spreadsheet_id = os.getenv('SPREADSHEET_ID')
        self.sheet_name = os.getenv('SHEET_NAME', 'Pengeluaran+pemasukan')
        
        # Railway/Google Cloud Run compatible
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        if creds_json:
            # Railway environment variable
            creds_info = json.loads(creds_json)
            scopes = ['https://www.googleapis.com/auth/spreadsheets']
            creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        else:
            # Local development
            creds_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH')
            scopes = ['https://www.googleapis.com/auth/spreadsheets']
            creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        
        self.service = build('sheets', 'v4', credentials=creds)

    def append_data(self, data: dict):
        """Append new transaction to sheet"""
        values = [
            [
                data['date'],
                data['type'],  # 'Pemasukan' or 'Pengeluaran'
                data['amount'],
                data['description'],
                data['category'],
                data['source']  # 'manual' or 'struk'
            ]
        ]
        
        body = {'values': values}
        range_name = f"{self.sheet_name}!A:F"
        
        self.service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()

    def get_summary(self, days: int = 30) -> dict:
        """Get financial summary"""
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