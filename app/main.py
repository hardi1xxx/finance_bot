import os
import logging
from dotenv import load_dotenv
from .telegram_bot import create_app

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

if __name__ == '__main__':
    app = create_app()
    print("🤖 Bot started...")
    app.run_polling()