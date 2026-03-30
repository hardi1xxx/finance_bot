import json
import os
from urllib.parse import unquote_plus
import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GoogleSheetsManager:
    def __init__(self):
        self.spreadsheet_id = os.getenv('SPREADSHEET_ID')
        self.sheet_name = unquote_plus(os.getenv('SHEET_NAME', 'Sheet1'))

        if not self.spreadsheet_id:
            raise ValueError("SPREADSHEET_ID belum diset!")

        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')

        if creds_json:
            try:
                creds_info = json.loads(creds_json)
                creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(f"GOOGLE_CREDENTIALS_JSON invalid: {e}")
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

        try:
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A:F",  # Mulai dari A1, append akan otomatis
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': values}
            ).execute()
        except HttpError as e:
            raise RuntimeError(f"Google Sheets API error saat append data: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error saat append data: {e}") from e

    def get_summary(self):
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A1:F1000"  # Limit range untuk performa
            ).execute()

            rows = result.get('values', [])
            if len(rows) < 1:
                return dict(total_income=0, total_expense=0, balance=0, total_transactions=0)

            # Pastikan header ada
            if len(rows) < 2:
                return dict(total_income=0, total_expense=0, balance=0, total_transactions=0)

            df = pd.DataFrame(rows[1:], columns=rows[0])
            
            # Convert amount ke numeric dengan handling error
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
            df = df.dropna(subset=['amount', 'type'])  # Hapus row yang amount-nya invalid

            income = df[df['type'] == 'Pemasukan']['amount'].sum() or 0
            expense = df[df['type'] == 'Pengeluaran']['amount'].sum() or 0

            return {
                'total_income': float(income),
                'total_expense': float(expense),
                'balance': float(income - expense),
                'total_transactions': len(df)
            }
        except Exception as e:
            raise RuntimeError(f"Error saat get summary: {e}") from e