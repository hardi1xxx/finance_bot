import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
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
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "💰 *Bot Keuangan*\n\n"
            "Pilih aksi yang ingin dilakukan:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == 'scan_receipt':
            self.user_states[query.from_user.id] = 'waiting_receipt'
            await query.edit_message_text("📸 Kirim foto struk belanja Anda")
        
        elif query.data == 'manual_input':
            self.user_states[query.from_user.id] = 'manual_type'
            await query.edit_message_text(
                "➕ *Input Manual*\n\n"
                "Pilih: Pemasukan atau Pengeluaran?",
                parse_mode='Markdown'
            )
            keyboard = [
                [InlineKeyboardButton("💸 Pemasukan", callback_data='type_income')],
                [InlineKeyboardButton("💸 Pengeluaran", callback_data='type_expense')]
            ]
            await query.message.reply_text(
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif query.data == 'summary':
            summary = self.sheets.get_summary()
            text = (
                f"📊 *Ringkasan Keuangan*\n\n"
                f"💰 Total Pemasukan: Rp {summary['total_income']:,.0f}\n"
                f"💸 Total Pengeluaran: Rp {summary['total_expense']:,.0f}\n"
                f"💳 Saldo: Rp {summary['balance']:,.0f}\n"
                f"📝 Total Transaksi: {summary['total_transactions']}"
            )
            await query.edit_message_text(text, parse_mode='Markdown')

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in self.user_states or self.user_states[user_id] != 'waiting_receipt':
            await update.message.reply_text("Gunakan menu utama terlebih dahulu!")
            return
        
        # Download photo
        photo = await context.bot.get_file(update.message.photo[-1].file_id)
        image_bytes = await photo.download_as_bytearray()
        
        # OCR processing
        await update.message.reply_text("🔍 Sedang memproses struk...")
        result = self.ocr.extract_from_image(image_bytes)
        
        if not result['amounts']:
            await update.message.reply_text(
                "❌ Tidak dapat membaca nominal dari struk. "
                "Coba kirim ulang atau gunakan input manual."
            )
            return
        
        # Prepare data
        largest_amount = result['largest_amount']
        date = result['date']
        
        keyboard = [
            [InlineKeyboardButton("✅ Simpan Pengeluaran", callback_data=f'save_exp:{largest_amount}:{date}:{result["text"][:100]}')],
            [InlineKeyboardButton("❌ Batal", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📄 *Hasil OCR:*\n"
            f"💰 Nominal terbesar: Rp {largest_amount:,.0f}\n"
            f"📅 Tanggal: {date}\n"
            f"📝 Teks: {result['text'][:200]}...",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        del self.user_states[user_id]

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        if user_id not in self.user_states:
            return
        
        state = self.user_states[user_id]
        
        if state == 'manual_amount':
            try:
                amount = float(text.replace('.', '').replace(',', '.'))
                context.user_data['amount'] = amount
                self.user_states[user_id] = 'manual_desc'
                await update.message.reply_text("📝 Masukkan deskripsi transaksi:")
            except:
                await update.message.reply_text("❌ Format nominal salah! Contoh: 25000 atau 25.000")
        
        elif state == 'manual_desc':
            context.user_data['description'] = text
            self.user_states[user_id] = 'manual_save'
            
            category = categorize_transaction(text)
            amount = context.user_data['amount']
            trans_type = context.user_data['type']
            
            keyboard = [
                [InlineKeyboardButton("✅ Simpan", callback_data=f'manual_save:{amount}:{text}:{category}')],
                [InlineKeyboardButton("❌ Batal", callback_data='cancel')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"📝 *Konfirmasi*\n"
                f"💰 {trans_type}: Rp {amount:,.0f}\n"
                f"📄 Deskripsi: {text}\n"
                f"🏷️ Kategori: {category}",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data.split(':')
        
        if data[0] == 'save_exp':
            amount, date, desc = data[1], data[2], ':'.join(data[3:])
            category = categorize_transaction(desc)
            
            self.sheets.append_data({
                'date': date,
                'type': 'Pengeluaran',
                'amount': amount,
                'description': desc[:100],
                'category': category,
                'source': 'struk'
            })
            
            await query.edit_message_text(
                f"✅ *Berhasil disimpan!*\n\n"
                f"💸 Pengeluaran: Rp {float(amount):,.0f}\n"
                f"📅 {date}\n"
                f"🏷️ {category}",
                parse_mode='Markdown'
            )
        
        elif data[0] == 'type_income':
            context.user_data['type'] = 'Pemasukan'
            self.user_states[query.from_user.id] = 'manual_amount'
            await query.message.reply_text("💰 Masukkan nominal pemasukan (contoh: 500000)")
        
        elif data[0] == 'type_expense':
            context.user_data['type'] = 'Pengeluaran'
            self.user_states[query.from_user.id] = 'manual_amount'
            await query.message.reply_text("💸 Masukkan nominal pengeluaran (contoh: 25000)")
        
        elif data[0] == 'manual_save':
            amount, desc, category = data[1], data[2], data[3]
            trans_type = context.user_data.get('type', 'Pengeluaran')
            
            self.sheets.append_data({
                'date': datetime.now().strftime('%d/%m/%Y'),
                'type': trans_type,
                'amount': amount,
                'description': desc,
                'category': category,
                'source': 'manual'
            })
            
            await query.edit_message_text(
                f"✅ *Berhasil disimpan!*\n\n"
                f"💰 {trans_type}: Rp {float(amount):,.0f}\n"
                f"📄 {desc}\n"
                f"🏷️ {category}",
                parse_mode='Markdown'
            )
            del self.user_states[query.from_user.id]

def create_app():
    application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
    bot = FinanceBot()
    
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CallbackQueryHandler(bot.button_handler))
    application.add_handler(CallbackQueryHandler(bot.callback_handler))
    application.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    
    return application