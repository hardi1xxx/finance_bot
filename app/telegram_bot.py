import os
import logging
from datetime import datetime
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)

from .google_sheets import GoogleSheetsManager
from .utils import parse_transaction
from .ocr import OCRProcessor

logger = logging.getLogger(__name__)


class FinanceBot:
    def __init__(self):
        self.sheets = GoogleSheetsManager()
        self.ocr = OCRProcessor()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("📊 Lihat Summary", callback_data='summary')],
            [InlineKeyboardButton("ℹ️ Bantuan", callback_data='help')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "💰 *Bot Keuangan AI*\n\n"
            "📝 Cara pakai:\n"
            "• makan 25rb\n"
            "• gaji 3jt\n"
            "• Kirim foto struk 📸",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == 'summary':
            await self._show_summary(query)

    async def _show_summary(self, query):
        s = self.sheets.get_summary()

        text = (
            f"📊 *Summary*\n\n"
            f"💰 Pemasukan: Rp {s['total_income']:,.0f}\n"
            f"💸 Pengeluaran: Rp {s['total_expense']:,.0f}\n"
            f"💳 Saldo: Rp {s['balance']:,.0f}\n"
        )

        await query.edit_message_text(text, parse_mode='Markdown')

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return

        text = update.message.text.strip()

        # filter group
        if update.message.chat.type in ["group", "supergroup"]:
            if "@KeuanganQita_BOT" not in text:
                return
            text = text.replace("@KeuanganQita_BOT", "").strip()

        try:
            data = parse_transaction(text)

            self.sheets.append_data({
                'date': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'type': data['type'],
                'amount': data['amount'],
                'description': data['description'],
                'category': data['category'],
                'source': 'text'
            })

            await update.message.reply_text(
                f"✅ Rp {data['amount']:,.0f} tersimpan"
            )

        except Exception:
            await update.message.reply_text("❌ Format salah")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            photo = await context.bot.get_file(update.message.photo[-1].file_id)
            image_bytes = await photo.download_as_bytearray()

            result = self.ocr.extract_from_image(image_bytes)
            amount = result.get('largest_amount', 0)

            if amount == 0:
                await update.message.reply_text("❌ Tidak terbaca")
                return

            self.sheets.append_data({
                'date': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'type': 'Pengeluaran',
                'amount': amount,
                'description': 'OCR',
                'category': 'Lainnya',
                'source': 'ocr'
            })

            await update.message.reply_text(f"✅ Rp {amount:,.0f}")

        except Exception:
            await update.message.reply_text("❌ OCR gagal")

    async def summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        s = self.sheets.get_summary()

        text = (
            f"📊 *Summary*\n\n"
            f"💰 Pemasukan: Rp {s['total_income']:,.0f}\n"
            f"💸 Pengeluaran: Rp {s['total_expense']:,.0f}\n"
            f"💳 Saldo: Rp {s['balance']:,.0f}\n"
        )

        await update.message.reply_text(text, parse_mode='Markdown')


def create_app():
    token = os.getenv('TELEGRAM_BOT_TOKEN')

    app = Application.builder().token(token).build()
    bot = FinanceBot()

    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("summary", bot.summary))
    app.add_handler(CallbackQueryHandler(bot.button_callback))
    app.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))

    return app