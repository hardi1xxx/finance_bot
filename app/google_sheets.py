import json
import os
import time
from urllib.parse import unquote_plus
import logging

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GoogleSheetsManager:
    def __init__(self):
        self.spreadsheet_id = os.getenv('SPREADSHEET_ID')
        self.sheet_name = unquote_plus(os.getenv('SHEET_NAME', 'Sheet1'))

        logger.info(f"🌐 Env - SPREADSHEET_ID: {self.spreadsheet_id[:20]}...")
        logger.info(f"🌐 Env - SHEET_NAME: {self.sheet_name}")

        if not self.spreadsheet_id:
            raise ValueError("SPREADSHEET_ID kosong! Set di Railway dashboard")

        self.scopes = ['https://www.googleapis.com/auth/spreadsheets']

        creds_json_raw = os.getenv('GOOGLE_CREDENTIALS_JSON')
        if not creds_json_raw:
            raise ValueError("GOOGLE_CREDENTIALS_JSON kosong! Set di Railway dashboard")

        try:
            # ✅ Parse JSON dulu (JANGAN diubah dulu)
            creds_info = json.loads(creds_json_raw)

            # ✅ Fix khusus private_key saja
            if "private_key" in creds_info:
                creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")

            # ✅ Validasi field penting
            required = ['client_email', 'private_key']
            missing = [k for k in required if k not in creds_info]
            if missing:
                raise ValueError(f"Missing credentials: {missing}")

            creds = Credentials.from_service_account_info(creds_info, scopes=self.scopes)
            logger.info(f"✅ Auth OK - {creds_info.get('client_email')}")

        except Exception as e:
            logger.error(f"❌ Auth failed: {e}")
            raise ValueError(f"Credentials invalid: {str(e)[:100]}...")

        # ✅ Build service dengan retry
        for attempt in range(3):
            try:
                self.service = build('sheets', 'v4', credentials=creds)

                # Test koneksi
                self.service.spreadsheets().get(
                    spreadsheetId=self.spreadsheet_id
                ).execute()

                logger.info("✅ Google Sheets connected!")
                break

            except Exception as e:
                logger.warning(f"Connection attempt {attempt+1} failed: {e}")
                if attempt == 2:
                    raise
                time.sleep(2)

    def append_data(self, data: dict):
        values = [[
            data.get('date', ''),
            data.get('type', ''),
            float(data.get('amount', 0)),
            data.get('description', '')[:50],
            data.get('category', ''),
            data.get('source', '')
        ]]

        for attempt in range(3):
            try:
                self.service.spreadsheets().values().append(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{self.sheet_name}!A:F",
                    valueInputOption='USER_ENTERED',
                    insertDataOption='INSERT_ROWS',
                    body={'values': values}
                ).execute()

                logger.info(f"✅ Saved: {data.get('description', '')[:30]}...")
                return True

            except HttpError as e:
                logger.error(f"HTTP {e.resp.status}: {e}")
                if e.resp.status == 429:
                    time.sleep(2 ** attempt)
                    continue
                raise

            except Exception as e:
                logger.error(f"Append error: {e}")
                if attempt == 2:
                    raise RuntimeError(f"Gagal simpan setelah 3x coba: {e}")
                time.sleep(1)

        return False

    def get_summary(self):
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A1:F"
            ).execute()

            rows = result.get('values', [])

            if len(rows) < 2:
                return {
                    'total_income': 0,
                    'total_expense': 0,
                    'balance': 0,
                    'total_transactions': 0
                }

            headers = [h.lower() for h in rows[0]]
            transactions = []

            for row in rows[1:]:
                if len(row) < 3:
                    continue

                try:
                    amount_idx = headers.index('amount')
                    type_idx = headers.index('type')

                    amount = float(str(row[amount_idx]).replace(',', ''))
                    trans_type = str(row[type_idx]).lower()

                    transactions.append({
                        'amount': amount,
                        'type': trans_type
                    })

                except:
                    continue

            income = sum(t['amount'] for t in transactions if 'pemasukan' in t['type'])
            expense = sum(t['amount'] for t in transactions if 'pengeluaran' in t['type'])

            logger.info(f"📊 Summary: {len(transactions)} tx")

            return {
                'total_income': float(income),
                'total_expense': float(expense),
                'balance': float(income - expense),
                'total_transactions': len(transactions)
            }

        except Exception as e:
            logger.error(f"Summary error: {e}")
            return {
                'total_income': 0,
                'total_expense': 0,
                'balance': 0,
                'total_transactions': 0
            }