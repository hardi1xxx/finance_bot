import os
from flask import Flask, render_template
from app.google_sheets import GoogleSheetsManager

app = Flask(__name__)
sheets = GoogleSheetsManager()

@app.route("/")
def dashboard():
    s = sheets.get_summary()

    return render_template(
        "index.html",
        income=s['total_income'],
        expense=s['total_expense'],
        balance=s['balance']
    )