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
        await update.message.reply_text(
            "💰 *Bot Keuangan AI*\n\n"
            "Ketik langsung contoh:\n"
            "- makan 25rb\n"
            "- gaji 3jt\n\n"
            "Atau kirim foto struk 📸",
            parse_mode='Markdown'
        )

    # =========================
    # TEXT AI AUTO INPUT
    # =========================
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return

        text = update.message.text

        try:
            data = parse_transaction(text)

            self.sheets.append_data({
                'date': datetime.now().strftime('%d/%m/%Y'),
                'type': data['type'],
                'amount': data['amount'],
                'description': data['description'],
                'category': data['category'],
                'source': 'ai_text'
            })

            await update.message.reply_text(
                f"✅ *Tercatat otomatis*\n\n"
                f"💰 Rp {data['amount']:,.0f}\n"
                f"📂 {data['category']}\n"
                f"📝 {data['description']}",
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"Error parsing text: {e}")
            await update.message.reply_text("❌ Tidak bisa membaca input\nContoh: makan 25rb")

    # =========================
    # OCR FOTO
    # =========================
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            photo = await context.bot.get_file(update.message.photo[-1].file_id)
            image_bytes = await photo.download_as_bytearray()

            await update.message.reply_text("🔍 Membaca struk...")

            result = self.ocr.extract_from_image(image_bytes)

            amount = result.get('largest_amount', 0)

            if amount == 0:
                await update.message.reply_text("❌ Tidak menemukan nominal")
                return

            self.sheets.append_data({
                'date': datetime.now().strftime('%d/%m/%Y'),
                'type': 'Pengeluaran',
                'amount': amount,
                'description': 'OCR Struk',
                'category': 'Lainnya',
                'source': 'ocr'
            })

            await update.message.reply_text(
                f"📸 *Struk terbaca*\n\n"
                f"💰 Rp {amount:,.0f}",
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"OCR error: {e}")
            await update.message.reply_text("❌ Gagal membaca gambar")

    # =========================
    # SUMMARY
    # =========================
    async def summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        s = self.sheets.get_summary()

        await update.message.reply_text(
            f"📊 *Summary*\n\n"
            f"💰 Pemasukan: Rp {s['total_income']:,.0f}\n"
            f"💸 Pengeluaran: Rp {s['total_expense']:,.0f}\n"
            f"💳 Saldo: Rp {s['balance']:,.0f}\n"
            f"📝 Transaksi: {s['total_transactions']}",
            parse_mode='Markdown'
        )


# =========================
# CREATE APP
# =========================
def create_app():
    token = os.getenv('TELEGRAM_BOT_TOKEN')

    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN belum diset!")

    app = Application.builder().token(token).build()
    bot = FinanceBot()

    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("summary", bot.summary))

    app.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))

    return app