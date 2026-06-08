import os
import json
from datetime import datetime
from flask import request, Flask, render_template
from app.google_sheets import GoogleSheetsManager

app = Flask(__name__)

@app.route("/")
def dashboard():
    sheets = GoogleSheetsManager()
    data = sheets.get_summary()

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

            date_obj = datetime.strptime(raw_date.split(" ")[0], "%d/%m/%Y")

            if selected_month:
                filter_date = datetime.strptime(selected_month, "%Y-%m")
                if date_obj.year != filter_date.year or date_obj.month != filter_date.month:
                    continue

            transactions.append({
                "date":        raw_date,
                "type":        r[1],
                "amount":      amount,
                "description": r[3].strip() if len(r) > 3 and r[3] else "",  # ← kolom D
                "category":    r[4].strip() if len(r) > 4 and r[4] else "",  # ← kolom E
                "source":      r[5].strip() if len(r) > 5 and r[5] else "",  # ← kolom F
            })

        except:
            continue

    return render_template(
        "index.html",
        summary=data,
        transactions=transactions,
        transactions_json=json.dumps(transactions, ensure_ascii=False),
        selected_month=selected_month
    )