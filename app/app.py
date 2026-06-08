import os
import json
from datetime import datetime
from flask import request, Flask, render_template
from app.google_sheets import GoogleSheetsManager

app = Flask(__name__)

@app.route("/")
def dashboard():
    sheets = GoogleSheetsManager()

    # ✅ Default ke bulan ini kalau tidak ada parameter
    selected_month = request.args.get("month") or datetime.now().strftime("%Y-%m")

    # ✅ Ambil semua baris data dari sheet (tanpa filter di sini)
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

            raw_date = str(r[0]).strip()
            raw_amount = str(r[2]).replace("Rp", "").replace(".", "").replace(",", "").strip()
            amount = float(raw_amount) if raw_amount else 0

            # ✅ Support format DD/MM/YYYY dan YYYY-MM-DD
            date_clean = raw_date.split(" ")[0]
            if "/" in date_clean:
                date_obj = datetime.strptime(date_clean, "%d/%m/%Y")
            else:
                date_obj = datetime.strptime(date_clean, "%Y-%m-%d")

            # ✅ Filter berdasarkan bulan yang dipilih
            row_month = date_obj.strftime("%Y-%m")
            if row_month != selected_month:
                continue

            # ✅ Simpan tanggal dalam format konsisten untuk JS (DD/MM/YYYY)
            transactions.append({
                "date":        date_obj.strftime("%d/%m/%Y"),
                "date_sort":   date_obj.strftime("%Y-%m-%d"),  # untuk sorting di JS
                "type":        str(r[1]).strip() if len(r) > 1 else "",
                "amount":      amount,
                "description": str(r[3]).strip() if len(r) > 3 and r[3] else "",
                "category":    str(r[4]).strip() if len(r) > 4 and r[4] else "",
                "source":      str(r[5]).strip() if len(r) > 5 and r[5] else "",
            })

        except Exception as e:
            continue  # skip baris rusak

    # ✅ Hitung summary dari transactions yang sudah difilter (bukan dari get_summary)
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