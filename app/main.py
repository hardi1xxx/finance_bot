import logging
import sys
import threading
import os

from app.telegram_bot import create_app
from app.app import app as flask_app  # ← dashboard

# Debug logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

def run_bot():
    try:
        bot = create_app()
        print("🚀 Bot started!")
        bot.run_polling(drop_pending_updates=True)
    except Exception as e:
        logging.error(f"Bot error: {e}", exc_info=True)

def run_web():
    port = int(os.environ.get("PORT", 8000))
    print(f"🌐 Web running on port {port}")
    flask_app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # jalanin bot di background
    threading.Thread(target=run_bot).start()

    # jalanin web (utama Railway)
    run_web()