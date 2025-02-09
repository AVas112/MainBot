import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging():
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Set up logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Create a file handler for logging to a file
    file_handler = RotatingFileHandler(
        'logs/bot.log',
        maxBytes=1024 * 1024,  # 1 MB
        backupCount=5
    )
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    # Get the root logger and add the file handler
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)

    return root_logger
