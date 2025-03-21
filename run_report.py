import asyncio
import logging
from dotenv import load_dotenv
import sys

# Устанавливаем кодировку для вывода
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Загружаем переменные окружения из .env файла
load_dotenv()

from src.daily_report import DailyReport

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        encoding='utf-8'
    )
    # Создаем экземпляр DailyReport без бота для автономной работы
    report = DailyReport()
    asyncio.run(report.main())
