import os
import json
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
            date = r[0]
            amount = float(r[2])

            # filter bulan
            if selected_month:
                if selected_month not in date:
                    continue

            transactions.append({
                "date": date,
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
        
        
    
