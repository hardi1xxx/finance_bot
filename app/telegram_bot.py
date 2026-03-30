import os
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)

from .google_sheets import GoogleSheetsManager
from .utils import categorize_transaction


class FinanceBot:
    def __init__(self):
        self.sheets = GoogleSheetsManager()
        self.user_states = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("➕ Input", callback_data='input')],
            [InlineKeyboardButton("📊 Summary", callback_data='summary')]
        ]

        await update.message.reply_text(
            "💰 Bot Keuangan",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == 'input':
            self.user_states[query.from_user.id] = 'amount'
            await query.message.reply_text("Masukkan nominal:")

        elif query.data == 'summary':
            s = self.sheets.get_summary()

            await query.edit_message_text(
                f"📊 Summary\n\n"
                f"Pemasukan: Rp {s['total_income']:,.0f}\n"
                f"Pengeluaran: Rp {s['total_expense']:,.0f}\n"
                f"Saldo: Rp {s['balance']:,.0f}"
            )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if user_id not in self.user_states:
            return

        try:
            amount = float(update.message.text.replace('.', '').replace(',', '.'))

            self.sheets.append_data({
                'date': datetime.now().strftime('%d/%m/%Y'),
                'type': 'Pengeluaran',
                'amount': amount,
                'description': 'Manual',
                'category': 'Umum',
                'source': 'manual'
            })

            await update.message.reply_text("✅ Tersimpan")
            del self.user_states[user_id]

        except:
            await update.message.reply_text("❌ Format salah")


def create_app():
    token = os.getenv('TELEGRAM_BOT_TOKEN')

    app = Application.builder().token(token).build()
    bot = FinanceBot()

    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CallbackQueryHandler(bot.button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))

    return app