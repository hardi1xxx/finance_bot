import os
import json
from datetime import datetime
from flask import request, Flask, render_template
from app.google_sheets import GoogleSheetsManager

app = Flask(__name__)

@app.route("/")
def dashboard():
    sheets = GoogleSheetsManager()

    # Default ke bulan ini kalau tidak ada parameter
    selected_month = request.args.get("month") or datetime.now().strftime("%Y-%m")

    # Ambil semua baris data dari sheet (mulai A2 agar skip header)
    result = sheets.service.spreadsheets().values().get(
        spreadsheetId=sheets.spreadsheet_id,
        range=f"{sheets.sheet_name}!A2:F"
    ).execute()

    rows = result.get("values", [])
    transactions = []

    for r in rows:
        try:
            if len(r) < 3:
                continue

            raw_date = str(r[0]).strip()  # contoh: "07/04/2026 2:47"
            
            # Ambil bagian tanggal saja (buang jam)
            date_part = raw_date.split(" ")[0]  # "07/04/2026"
            
            # Parse DD/MM/YYYY
            date_obj = datetime.strptime(date_part, "%d/%m/%Y")

            # Filter bulan yang dipilih
            row_month = date_obj.strftime("%Y-%m")
            if row_month != selected_month:
                continue

            # Parse nominal — handle titik sebagai pemisah ribuan
            raw_amount = str(r[2]).replace("Rp", "").replace(".", "").replace(",", "").strip()
            amount = float(raw_amount) if raw_amount else 0

            transactions.append({
                "date":        date_obj.strftime("%d/%m/%Y"),
                "date_sort":   date_obj.strftime("%Y-%m-%d"),
                "type":        str(r[1]).strip() if len(r) > 1 else "",
                "amount":      amount,
                "description": str(r[3]).strip() if len(r) > 3 and r[3] else "",  # kolom D = Deskripsi
                "category":    str(r[4]).strip() if len(r) > 4 and r[4] else "",  # kolom E = Kategori
                "source":      str(r[5]).strip() if len(r) > 5 and r[5] else "",  # kolom F = Sumber
            })

        except Exception as e:
            continue

    # Hitung summary dari data yang sudah difilter
    total_income  = sum(t["amount"] for t in transactions if "pemasukan"   in t["type"].lower())
    total_expense = sum(t["amount"] for t in transactions if "pengeluaran" in t["type"].lower())

    summary = {
        "total_income":       total_income,
        "total_expense":      total_expense,
        "balance":            total_income - total_expense,
        "total_transactions": len(transactions),
    }

    return render_template(
        "index.html",
        summary=summary,
        transactions=transactions,
        transactions_json=json.dumps(transactions, ensure_ascii=False),
        selected_month=selected_month
    )