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
            "📝 *Cara pakai:*\n"
            "• `makan 25rb`\n"
            "• `gaji 3jt`\n"
            "• Kirim foto struk 📸\n\n"
            "*Contoh kategori:*\n"
            "• Makanan: makan, jajan, kopi\n"
            "• Transport: bensin, gojek",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == 'summary':
            await self._show_summary(query)
        elif query.data == 'help':
            await query.edit_message_text(
                "💡 *Bantuan*\n\n"
                "• Ketik nominal + keterangan\n"
                "• Format: `25rb`, `3jt`, `10000`\n"
                "• Kirim foto struk untuk OCR\n"
                "• `/summary` untuk ringkasan",
                parse_mode='Markdown'
            )

    async def _show_summary(self, query):
        try:
            s = self.sheets.get_summary()
            text = (
                f"📊 *Summary Keuangan*\n\n"
                f"💰 *Pemasukan:* Rp {s['total_income']:,.0f}\n"
                f"💸 *Pengeluaran:* Rp {s['total_expense']:,.0f}\n"
                f"💳 *Saldo:* Rp {s['balance']:,.0f}\n"
                f"📈 *Total Transaksi:* {s['total_transactions']}"
            )
            await query.edit_message_text(text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Summary error: {e}")
            await query.edit_message_text("❌ Gagal load summary")

    # =========================
    # TEXT AI AUTO INPUT
    # =========================
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return

        text = update.message.text.strip()

        try:
            data = parse_transaction(text)
            
            self.sheets.append_data({
                'date': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'type': data['type'],
                'amount': data['amount'],
                'description': data['description'][:50],  # Limit description
                'category': data['category'],
                'source': 'text'
            })

            emoji = "💰" if data['type'] == 'Pemasukan' else "💸"
            await update.message.reply_text(
                f"✅ *Berhasil disimpan!*\n\n"
                f"{emoji} Rp {data['amount']:,.0f}\n"
                f"📂 {data['category']}\n"
                f"📝 {data['description']}",
                parse_mode='Markdown'
            )

        except ValueError as e:
            logger.warning(f"Parse error: {e}")
            await update.message.reply_text(
                f"❌ {str(e)}\n\n"
                "*Contoh:*\n"
                "• `makan 25rb`\n"
                "• `gaji 3jt`",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Text handler error: {e}")
            await update.message.reply_text("❌ Error sistem, coba lagi")

    # =========================
    # OCR FOTO
    # =========================
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            photo = await context.bot.get_file(update.message.photo[-1].file_id)
            image_bytes = await photo.download_as_bytearray()

            await update.message.reply_chat_action('typing')
            await update.message.reply_text("🔍 Membaca struk... ⏳")

            result = self.ocr.extract_from_image(image_bytes)

            amount = result.get('largest_amount', 0)

            if amount == 0:
                await update.message.reply_text(
                    "❌ Tidak menemukan nominal di struk\n"
                    "Coba ambil foto lebih jelas 📸"
                )
                return

            self.sheets.append_data({
                'date': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'type': 'Pengeluaran',
                'amount': amount,
                'description': f'Struk OCR - {result.get("text", "")[:30]}',
                'category': 'Lainnya',
                'source': 'ocr'
            })

            await update.message.reply_text(
                f"✅ *Struk terbaca otomatis!*\n\n"
                f"💸 Rp {amount:,.0f}\n"
                f"📂 Lainnya\n"
                f"📸 Struk OCR",
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"OCR handler error: {e}")
            await update.message.reply_text("❌ Gagal membaca gambar\nPastikan foto jelas dan berisi nominal")

    # =========================
    # SUMMARY COMMAND
    # =========================
    async def summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            await update.message.reply_chat_action('typing')
            s = self.sheets.get_summary()
            
            text = (
                f"📊 *Summary Keuangan*\n\n"
                f"💰 *Pemasukan:* Rp {s['total_income']:,.0f}\n"
                f"💸 *Pengeluaran:* Rp {s['total_expense']:,.0f}\n"
                f"💳 *Saldo:* Rp {s['balance']:,.0f}\n"
                f"📈 *Total Transaksi:* {s['total_transactions']}"
            )
            await update.message.reply_text(text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Summary command error: {e}")
            await update.message.reply_text("❌ Gagal load summary")


# =========================
# CREATE APP
# =========================
def create_app():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN belum diset!")

    app = Application.builder().token(token).build()
    bot = FinanceBot()

    # Command handlers
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("summary", bot.summary))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(bot.button_callback))
    
    # Message handlers
    app.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))

    logger.info("✅ Telegram bot handlers registered")
    return app