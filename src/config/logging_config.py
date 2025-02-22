import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

def setup_logging():
    """Sets up logging system with UTF-8 support and file rotation.

    The function performs the following actions:
    1. Creates 'logs' directory if it doesn't exist
    2. Configures basic logging with INFO level
    3. Creates rotating file handler for logs
    4. Adds file handler to the root logger

    Returns
    -------
    logging.Logger
        Configured root logger with added file handler

    Notes
    -----
    - Logs are saved to 'logs/bot.log'
    - Maximum log file size: 1 MB
    - Keeps up to 5 files with rotation
    - All logs are written in UTF-8 encoding
    """
    # Create logs directory if it doesn't exist
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)


    # Set up logging configuration with UTF-8
    logging.basicConfig(
        level=logging.INFO,
        format='${asctime} - ${name} - ${levelname} - ${message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        encoding='utf-8',
        style='$'
    )


    # Reconfigure default stream handlers to use UTF-8 encoding.
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.stream.reconfigure(encoding="utf-8")


    # Create a file handler for logging to a file with UTF-8
    file_handler = RotatingFileHandler(
        log_dir / 'bot.log',
        maxBytes=1024 * 1024,  # 1 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter('${asctime} - ${name} - ${levelname} - ${message}', style='$'))


    # Get the root logger and add a file handler to it
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
