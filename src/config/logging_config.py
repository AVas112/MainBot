import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


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
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)


    logging.basicConfig(
        level=logging.INFO,
        format="${asctime} - ${name} - ${levelname} - ${message}",
        datefmt="%Y-%m-%d %H:%M:%S",
        encoding="utf-8",
        style="$"
    )


    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.stream.reconfigure(encoding="utf-8")


    file_handler = RotatingFileHandler(
        log_dir / "bot.log",
        maxBytes=1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter("${asctime} - ${name} - ${levelname} - ${message}", style="$"))


    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
