import logging
import sys
from app.telegram_bot import create_app

# Debug logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,  # Ubah ke DEBUG untuk troubleshooting
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

if __name__ == "__main__":
    try:
        app = create_app()
        print("🚀 Bot started! Test dengan /test")
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)