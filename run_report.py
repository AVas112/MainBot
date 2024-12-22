import asyncio
import logging
from dotenv import load_dotenv
import os
import sys

# Устанавливаем кодировку для вывода
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Загружаем переменные окружения из .env файла
load_dotenv()

from bot.daily_report import DailyReport

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        encoding='utf-8'
    )
    asyncio.run(DailyReport().main())
