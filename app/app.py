import os
import json
from flask import Flask, render_template
from app.google_sheets import GoogleSheetsManager

app = Flask(__name__)

@app.route("/")
def dashboard():
    sheets = GoogleSheetsManager()
    data = sheets.get_summary()

    # 🔥 Tambahan: ambil semua data (buat chart)
    result = sheets.service.spreadsheets().values().get(
        spreadsheetId=sheets.spreadsheet_id,
        range=f"{sheets.sheet_name}!A2:F"
    ).execute()

    rows = result.get("values", [])

    transactions = []
    for r in rows:
        try:
            transactions.append({
                "date": r[0],
                "type": r[1],
                "amount": float(r[2])
            })
        except:
            continue

    # pisahkan data
    income_list = []
    expense_list = []

    for t in transactions:
        if "pemasukan" in t["type"].lower():
            income_list.append(t)
        else:
            expense_list.append(t)

    return render_template(
        "index.html",
        summary=data,
        transactions=json.dumps(transactions),
        income=data["total_income"],
        expense=data["total_expense"]
    )
        
        
    
