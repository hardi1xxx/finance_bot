import os
import json
from datetime import datetime
from flask import request
from flask import Flask, render_template
from app.google_sheets import GoogleSheetsManager

app = Flask(__name__)

@app.route("/")
@app.route("/")
def dashboard():
    sheets = GoogleSheetsManager()
    data = sheets.get_summary()

    # ambil parameter bulan (format: 2026-04)
    selected_month = request.args.get("month")

    result = sheets.service.spreadsheets().values().get(
        spreadsheetId=sheets.spreadsheet_id,
        range=f"{sheets.sheet_name}!A2:F"
    ).execute()

    rows = result.get("values", [])

    transactions = []

for r in rows:
    try:
        raw_date = r[0]
        amount = float(r[2])

        # ubah string ke datetime
        date_obj = datetime.strptime(raw_date.split(" ")[0], "%d/%m/%Y")

        # filter bulan
        if selected_month:
            filter_date = datetime.strptime(selected_month, "%Y-%m")

            if date_obj.year != filter_date.year or date_obj.month != filter_date.month:
                continue

        transactions.append({
            "date": raw_date,
            "type": r[1],
            "amount": amount
        })

    except:
        continue

    return render_template(
        "index.html",
        summary=data,
        transactions=transactions,
        transactions_json=json.dumps(transactions),
        selected_month=selected_month
    )
        
        
    
