import os
import logging
from datetime import datetime

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
            "• Kirim foto struk 📸\n\n"
            "🌐 Dashboard:\n"
            "https://financebot-production-a928.up.railway.app",
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
            f"🔢 Transaksi: {s['total_transactions']}"
        )

        await query.edit_message_text(text, parse_mode='Markdown')

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return

        text = update.message.text.strip()

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

        except Exception as e:
            logger.error(f"handle_text error: {e}")
            await update.message.reply_text("❌ Format salah")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            photo = await context.bot.get_file(update.message.photo[-1].file_id)
            image_bytes = await photo.download_as_bytearray()

            result = self.ocr.extract_from_image(image_bytes)
            amount = result.get('largest_amount', 0)
            merchant = result.get('description', 'Struk')
            date_ocr = result.get('date', '-')

            logger.info(f"handle_photo: amount={amount}, merchant={merchant}, date={date_ocr}")

            if amount == 0:
                await update.message.reply_text(
                    f"❌ Nominal tidak terbaca.\n\n"
                    f"🔍 Debug:\n"
                    f"merchant: {merchant}\n"
                    f"date: {date_ocr}\n"
                    f"raw: {result.get('text', 'kosong')[:300]}"
                )
                return

            self.sheets.append_data({
                'date': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'type': 'Pengeluaran',
                'amount': amount,
                'description': f'OCR: {merchant}',
                'category': 'Lainnya',
                'source': 'ocr'
            })

            await update.message.reply_text(
                f"✅ *{merchant}*\n"
                f"💸 Rp {amount:,.0f}\n"
                f"📅 {date_ocr}",
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"handle_photo error: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Error: {str(e)[:200]}"
            )

    async def summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        s = self.sheets.get_summary()

        text = (
            f"📊 *Summary*\n\n"
            f"💰 Pemasukan: Rp {s['total_income']:,.0f}\n"
            f"💸 Pengeluaran: Rp {s['total_expense']:,.0f}\n"
            f"💳 Saldo: Rp {s['balance']:,.0f}\n"
            f"🔢 Transaksi: {s['total_transactions']}"
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