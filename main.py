from src.telegram_bot import TelegramBot
from src.config.logging_config import setup_logging
from src.config.config import CONFIG

if __name__ == "__main__":
    # Set up logging
    logger = setup_logging()

    # Verify the token is loaded correctly (without revealing it entirely)
    token = CONFIG.TELEGRAM.BOT_TOKEN
    if token is not None:
        logger.info(f"Token loaded successfully. First 5 characters: {token[:5]}...")
    else:
        logger.error("Failed to load TELEGRAM_BOT_TOKEN from environment variables.")

    # Create and run the Telegram bot
    bot = TelegramBot()
    logger.info(f"Loaded threads: {bot.threads}")  # Check loaded threads
    bot.run()
