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
            creds_info = json.loads(creds_json_raw)

            if "private_key" in creds_info:
                creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")

            required = ['client_email', 'private_key']
            missing = [k for k in required if k not in creds_info]
            if missing:
                raise ValueError(f"Missing credentials: {missing}")

            creds = Credentials.from_service_account_info(creds_info, scopes=self.scopes)
            logger.info(f"✅ Auth OK - {creds_info.get('client_email')}")

        except Exception as e:
            logger.error(f"❌ Auth failed: {e}")
            raise ValueError(f"Credentials invalid: {str(e)[:100]}...")

        for attempt in range(3):
            try:
                self.service = build('sheets', 'v4', credentials=creds)
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

    # ─────────────────────────────────────────────
    # Helper internal: ambil semua baris dari sheet
    # ─────────────────────────────────────────────
    def _fetch_rows(self):
        """Ambil semua baris data dari sheet, return (headers, data_rows)."""
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"{self.sheet_name}!A1:F"
        ).execute()

        rows = result.get('values', [])
        if len(rows) < 2:
            return [], []

        headers = [h.strip().lower() for h in rows[0]]
        return headers, rows[1:]

    # ─────────────────────────────────────────────
    # Parse satu baris jadi dict transaksi lengkap
    # ─────────────────────────────────────────────
    def _parse_row(self, row, headers):
        """
        Mapping kolom sheet:
          A = tanggal   (index 0)
          B = jenis     (index 1)
          C = nominal   (index 2)
          D = keterangan(index 3)  ← yang sebelumnya kosong
          E = kategori  (index 4)
          F = sumber    (index 5)
        """
        try:
            # Cari index kolom dari header, fallback ke posisi default
            amount_idx = headers.index('nominal')      if 'nominal'      in headers else 2
            type_idx   = headers.index('jenis')        if 'jenis'        in headers else 1
            date_idx   = headers.index('tanggal')      if 'tanggal'      in headers else 0
            # Kolom D di sheet bernama "Deskripsi" — cek kedua kemungkinan nama
            desc_idx   = headers.index('deskripsi')    if 'deskripsi'    in headers else \
                         headers.index('keterangan')   if 'keterangan'   in headers else 3
            cat_idx    = headers.index('kategori')     if 'kategori'     in headers else 4
            src_idx    = headers.index('sumber')       if 'sumber'       in headers else 5

            amount = float(
                str(row[amount_idx])
                .replace(',', '')
                .replace('.', '')   # handle format 1.000.000
                .replace('Rp', '')
                .strip()
            ) if len(row) > amount_idx and row[amount_idx] else 0

            return {
                'date':        str(row[date_idx]).strip()  if len(row) > date_idx  and row[date_idx]  else '',
                'type':        str(row[type_idx]).strip()  if len(row) > type_idx  and row[type_idx]  else '',
                'amount':      amount,
                'description': str(row[desc_idx]).strip()  if len(row) > desc_idx  and row[desc_idx]  else '',  # ← kolom D
                'category':    str(row[cat_idx]).strip()   if len(row) > cat_idx   and row[cat_idx]   else '',
                'source':      str(row[src_idx]).strip()   if len(row) > src_idx   and row[src_idx]   else '',
            }
        except Exception as e:
            logger.warning(f"Skip row error: {e} | row: {row}")
            return None

    # ─────────────────────────────────────────────
    # Tambah data baru ke sheet
    # ─────────────────────────────────────────────
    def append_data(self, data: dict):
        values = [[
            data.get('date', ''),
            data.get('type', ''),
            float(data.get('amount', 0)),
            data.get('description', '')[:50],   # kolom D
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

    # ─────────────────────────────────────────────
    # Ambil daftar transaksi lengkap (dengan keterangan)
    # ─────────────────────────────────────────────
    def get_transactions(self, month_filter: str = None):
        """
        Return list of dict transaksi lengkap termasuk kolom D (keterangan).
        month_filter: string format 'YYYY-MM', misal '2025-06'. Kalau None, ambil semua.
        """
        try:
            headers, data_rows = self._fetch_rows()
            if not data_rows:
                return []

            transactions = []
            for row in data_rows:
                parsed = self._parse_row(row, headers)
                if not parsed:
                    continue

                # Filter bulan jika diminta
                if month_filter:
                    # Asumsikan format tanggal: DD/MM/YYYY atau YYYY-MM-DD
                    date_str = parsed['date']
                    if '/' in date_str:
                        # Format DD/MM/YYYY → ambil bulan & tahun
                        parts = date_str.split('/')
                        if len(parts) == 3:
                            row_month = f"{parts[2]}-{parts[1].zfill(2)}"
                        else:
                            row_month = ''
                    else:
                        # Format YYYY-MM-DD
                        row_month = date_str[:7]

                    if row_month != month_filter:
                        continue

                transactions.append(parsed)

            logger.info(f"📋 get_transactions: {len(transactions)} baris (filter={month_filter})")
            return transactions

        except Exception as e:
            logger.error(f"get_transactions error: {e}")
            return []

    # ─────────────────────────────────────────────
    # Ringkasan keuangan (summary)
    # ─────────────────────────────────────────────
    def get_summary(self, month_filter: str = None):
        """
        Return dict summary keuangan.
        Sekarang menggunakan get_transactions() supaya konsisten.
        """
        try:
            transactions = self.get_transactions(month_filter=month_filter)

            income  = sum(t['amount'] for t in transactions if 'pemasukan'   in t['type'].lower())
            expense = sum(t['amount'] for t in transactions if 'pengeluaran' in t['type'].lower())

            logger.info(f"📊 Summary: {len(transactions)} tx | in={income} | out={expense}")

            return {
                'total_income':      float(income),
                'total_expense':     float(expense),
                'balance':           float(income - expense),
                'total_transactions': len(transactions)
            }

        except Exception as e:
            logger.error(f"Summary error: {e}")
            return {
                'total_income':      0,
                'total_expense':     0,
                'balance':           0,
                'total_transactions': 0
            }