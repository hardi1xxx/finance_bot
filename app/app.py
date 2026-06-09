import os
import json
from datetime import datetime
from flask import request, Flask, render_template
from app.google_sheets import GoogleSheetsManager

app = Flask(__name__)

def parse_amount(raw):
    """
    Parse nominal dari Google Sheets.
    Handle: "62000", "62000.0", "62,000", "1.500.000", "Rp 62000"
    """
    s = str(raw).strip()
    s = s.replace("Rp", "").replace(" ", "")

    # Jika ada koma DAN titik → format ribuan campuran
    if "," in s and "." in s:
        # Misal "1.500,00" → titik=ribuan, koma=desimal
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        # Misal "62,000" → koma sebagai ribuan
        s = s.replace(",", "")
    elif "." in s:
        # Cek apakah titik sebagai ribuan atau desimal
        parts = s.split(".")
        if len(parts) > 2:
            # "1.500.000" → titik sebagai ribuan
            s = s.replace(".", "")
        elif len(parts) == 2 and len(parts[1]) == 3:
            # "62.000" → titik sebagai ribuan (3 digit setelah titik)
            s = s.replace(".", "")
        # else: "62000.0" → titik sebagai desimal, biarkan

    try:
        return float(s)
    except:
        return 0.0


@app.route("/")
def dashboard():
    sheets = GoogleSheetsManager()

    # Default ke bulan ini
    selected_month = request.args.get("month") or datetime.now().strftime("%Y-%m")

    # Ambil semua baris (skip header di baris 1)
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

            # Buang bagian jam: "07/04/2026 2:47" → "07/04/2026"
            date_part = raw_date.split(" ")[0]

            # Parse DD/MM/YYYY
            date_obj = datetime.strptime(date_part, "%d/%m/%Y")

            # Filter bulan
            row_month = date_obj.strftime("%Y-%m")
            if row_month != selected_month:
                continue

            amount = parse_amount(r[2])

            transactions.append({
                "date":        date_obj.strftime("%d/%m/%Y"),
                "date_sort":   date_obj.strftime("%Y-%m-%d"),
                "type":        str(r[1]).strip() if len(r) > 1 else "",
                "amount":      amount,
                "description": str(r[3]).strip() if len(r) > 3 and r[3] else "",
                "category":    str(r[4]).strip() if len(r) > 4 and r[4] else "",
                "source":      str(r[5]).strip() if len(r) > 5 and r[5] else "",
            })

        except Exception as e:
            continue

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