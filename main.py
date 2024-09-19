import logging
from dotenv import load_dotenv
from bot.telegram_bot import TelegramBot

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

if __name__ == '__main__':
    # Load environment variables
    load_dotenv()

    # Create and run the Telegram bot
    bot = TelegramBot()
    bot.run()
