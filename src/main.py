import logging

from src.config.config import CONFIG
from src.config.logging_config import setup_logging
from src.telegram_bot import TelegramBot


if __name__ == "__main__":
    setup_logging()

    token = CONFIG.TELEGRAM.BOT_TOKEN
    if token is not None:
        logging.info(f"Token loaded successfully. First 5 characters: {token[:5]}...")
    else:
        logging.error("Failed to load TELEGRAM_BOT_TOKEN from environment variables.")

    bot = TelegramBot()
    logging.info(f"Loaded threads: {bot.threads}")
    bot.run()
