import logging
import sys
import threading
import os

from app.telegram_bot import create_app
from app.app import app as flask_app

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def run_web():
    port = int(os.environ.get("PORT", 8080))
    print(f"🌐 Web running on port {port}")
    flask_app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # ✅ Web di background
    threading.Thread(target=run_web, daemon=True).start()

    # ✅ Bot WAJIB di main thread
    bot = create_app()
    print("🚀 Bot started!")
    bot.run_polling(drop_pending_updates=True)