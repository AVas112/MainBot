import os
from dotenv import load_dotenv
from bot.telegram_bot import TelegramBot
from config.logging_config import setup_logging

if __name__ == '__main__':
    # Load environment variables
    load_dotenv()

    # Set up logging
    logger = setup_logging()

    # Verify the token is loaded correctly (without revealing it entirely)
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if token:
        logger.info(f"Token loaded successfully. First 5 characters: {token[:5]}...")
    else:
        logger.error("Failed to load TELEGRAM_BOT_TOKEN from environment variables.")

    # Create and run the Telegram bot
    bot = TelegramBot()
    bot.run()
