import logging
import os
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)

from .ocr import OCRProcessor
from .google_sheets import GoogleSheetsManager
from .utils import categorize_transaction

logger = logging.getLogger(__name__)


class FinanceBot:
    def __init__(self):
        self.ocr = OCRProcessor()
        self.sheets = GoogleSheetsManager()
        self.user_states = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("📸 Scan Struk", callback_data='scan_receipt')],
            [InlineKeyboardButton("➕ Input Manual", callback_data='manual_input')],
            [InlineKeyboardButton("📊 Lihat Summary", callback_data='summary')]
        ]

        await update.message.reply_text(
            "💰 *Bot Keuangan*\n\nPilih aksi:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == 'scan_receipt':
            self.user_states[query.from_user.id] = 'waiting_receipt'
            await query.edit_message_text("📸 Kirim foto struk")

        elif query.data == 'manual_input':
            self.user_states[query.from_user.id] = 'manual_type'

            keyboard = [
                [InlineKeyboardButton("💰 Pemasukan", callback_data='type_income')],
                [InlineKeyboardButton("💸 Pengeluaran", callback_data='type_expense')]
            ]

            await query.edit_message_text(
                "➕ *Input Manual*\n\nPilih jenis:",
                parse_mode='Markdown'
            )

            await query.message.reply_text(
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif query.data == 'summary':
            summary = self.sheets.get_summary() or {
                'total_income': 0,
                'total_expense': 0,
                'balance': 0,
                'total_transactions': 0
            }

            await query.edit_message_text(
                f"📊 *Ringkasan*\n\n"
                f"💰 Pemasukan: Rp {summary['total_income']:,.0f}\n"
                f"💸 Pengeluaran: Rp {summary['total_expense']:,.0f}\n"
                f"💳 Saldo: Rp {summary['balance']:,.0f}\n"
                f"📝 Transaksi: {summary['total_transactions']}",
                parse_mode='Markdown'
            )

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if self.user_states.get(user_id) != 'waiting_receipt':
            await update.message.reply_text("Gunakan menu dulu!")
            return

        photo = await context.bot.get_file(update.message.photo[-1].file_id)
        image_bytes = await photo.download_as_bytearray()

        await update.message.reply_text("🔍 Processing...")

        result = self.ocr.extract_from_image(image_bytes)

        if not result['amounts']:
            await update.message.reply_text("❌ Gagal baca nominal")
            return

        amount = result['largest_amount']
        date = result['date']

        keyboard = [
            [InlineKeyboardButton("✅ Simpan", callback_data=f'save_exp:{amount}:{date}')],
            [InlineKeyboardButton("❌ Batal", callback_data='cancel')]
        ]

        await update.message.reply_text(
            f"💰 Rp {amount:,.0f}\n📅 {date}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        del self.user_states[user_id]

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if user_id not in self.user_states:
            return

        text = update.message.text.strip()
        state = self.user_states[user_id]

        if state == 'manual_amount':
            try:
                amount = float(text.replace('.', '').replace(',', '.'))
                context.user_data['amount'] = amount
                self.user_states[user_id] = 'manual_desc'
                await update.message.reply_text("📝 Deskripsi?")
            except:
                await update.message.reply_text("❌ Format salah")

        elif state == 'manual_desc':
            context.user_data['description'] = text
            category = categorize_transaction(text)

            keyboard = [
                [InlineKeyboardButton("✅ Simpan", callback_data=f'manual_save')],
                [InlineKeyboardButton("❌ Batal", callback_data='cancel')]
            ]

            await update.message.reply_text(
                f"💰 Rp {context.user_data['amount']:,.0f}\n"
                f"📝 {text}\n🏷️ {category}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        data = query.data.split(':')

        if data[0] == 'save_exp':
            amount, date = data[1], data[2]

            self.sheets.append_data({
                'date': date,
                'type': 'Pengeluaran',
                'amount': amount,
                'description': 'OCR',
                'category': 'Lainnya',
                'source': 'struk'
            })

            await query.edit_message_text("✅ Tersimpan!")

        elif data[0] == 'type_income':
            context.user_data['type'] = 'Pemasukan'
            self.user_states[query.from_user.id] = 'manual_amount'
            await query.message.reply_text("Nominal?")

        elif data[0] == 'type_expense':
            context.user_data['type'] = 'Pengeluaran'
            self.user_states[query.from_user.id] = 'manual_amount'
            await query.message.reply_text("Nominal?")

        elif data[0] == 'manual_save':
            self.sheets.append_data({
                'date': datetime.now().strftime('%d/%m/%Y'),
                'type': context.user_data['type'],
                'amount': context.user_data['amount'],
                'description': context.user_data['description'],
                'category': categorize_transaction(context.user_data['description']),
                'source': 'manual'
            })

            await query.edit_message_text("✅ Tersimpan!")

            del self.user_states[query.from_user.id]


def create_app():
    app = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
    bot = FinanceBot()

    app.add_handler(CommandHandler("start", bot.start))

    # Pisahin handler biar gak bentrok
    app.add_handler(CallbackQueryHandler(bot.button_handler, pattern="^(scan_receipt|manual_input|summary)$"))
    app.add_handler(CallbackQueryHandler(bot.callback_handler))

    app.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))

    return app