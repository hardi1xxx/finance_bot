import logging
from app.telegram_bot import create_app

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        app = create_app()
        logger.info("🚀 Starting Telegram Finance Bot...")
        app.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")