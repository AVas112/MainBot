import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from zoneinfo import ZoneInfo # Для корректной работы с временными зонами как в коде

# Загрузка конфигурации и установка переменных окружения
from dotenv import load_dotenv
load_dotenv(override=True)

import os
# Установка переменных для зависимых конфигов, если они не заданы
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake_telegram_token_for_testing")
os.environ.setdefault("OPENAI_API_KEY", "fake_openai_key_for_testing")
os.environ.setdefault("OPENAI_ASSISTANT_ID", "fake_assistant_id_for_testing")
os.environ.setdefault("SMTP_USER", "fake_user")
os.environ.setdefault("SMTP_PASSWORD", "fake_pass")
os.environ.setdefault("SMTP_SERVER", "fake_server")
os.environ.setdefault("SMTP_PORT", "587")
os.environ.setdefault("SMTP_USERNAME", "fake_username")
os.environ.setdefault("SMTP_NOTIFICATION_EMAIL", "fake_email@example.com")
os.environ.setdefault("REPORT_HOUR", "8") # Пример значения для .env
os.environ.setdefault("REPORT_MINUTE", "0") # Пример значения для .env
os.environ.setdefault("REMINDER_ENABLED", "False")

from src.config.config import CONFIG
from src.daily_report import DailyReport, logger as daily_report_logger
from src.database import Database # Нужен для мока db в DailyReport
from src.utils.email_service import email_service # Мокаем глобальный email_service

# --- Фикстуры ---

@pytest.fixture
def mock_db_for_report():
    db = AsyncMock(spec=Database)
    db.execute_fetch = AsyncMock()
    db.init_db = AsyncMock() # Мок для вызова в main
    return db

@pytest.fixture
def mock_email_service_global():
    # Мокаем глобальный email_service, который импортируется в daily_report.py
    with patch('src.daily_report.email_service', new_callable=AsyncMock) as mock_es:
        mock_es.send_email = AsyncMock()
        yield mock_es

@pytest.fixture
def mock_scheduler():
    scheduler = MagicMock()
    scheduler.add_job = MagicMock()
    scheduler.start = MagicMock()
    scheduler.running = False # Изначально не запущен
    return scheduler

@pytest.fixture
@patch('src.daily_report.Database') # Мокаем класс Database, чтобы он возвращал наш мок
@patch('apscheduler.schedulers.asyncio.AsyncIOScheduler') # Мокаем класс Scheduler
def daily_report_instance(MockAsyncIOScheduler, MockDatabase, 
                          mock_db_for_report, mock_scheduler, mock_email_service_global):
    MockDatabase.return_value = mock_db_for_report # Конструктор Database() вернет наш мок
    MockAsyncIOScheduler.return_value = mock_scheduler # Конструктор AsyncIOScheduler() вернет наш мок
    
    # Убедимся, что REPORT_HOUR и REPORT_MINUTE загружены в CONFIG
    assert CONFIG.REPORT.HOUR is not None
    assert CONFIG.REPORT.MINUTE is not None

    report_obj = DailyReport(telegram_bot=None) # telegram_bot не используется в тестируемых методах
    # Явно присваиваем моки, если нужно
    report_obj.db = mock_db_for_report
    report_obj.scheduler = mock_scheduler
    
    # Сохраняем моки для доступа в тестах
    report_obj._mock_db = mock_db_for_report
    report_obj._mock_scheduler = mock_scheduler
    report_obj._mock_email_service = mock_email_service_global
    return report_obj

# --- Тесты ---

@pytest.mark.asyncio
async def test_get_daily_dialogs(daily_report_instance: DailyReport):
    mock_dialog_data = [
        (1, "userA", "Hello", "user", "2023-01-01 10:00:00"),
        (1, "userA", "Hi bot", "assistant", "2023-01-01 10:01:00"),
        (2, "userB", "Question?", "user", "2023-01-01 11:00:00"),
    ]
    daily_report_instance._mock_db.execute_fetch.return_value = mock_dialog_data

    dialogs = await daily_report_instance.get_daily_dialogs()

    # Проверяем, что execute_fetch был вызван
    daily_report_instance._mock_db.execute_fetch.assert_called_once()
    # Проверяем аргументы SQL запроса (особенно дату)
    args, _ = daily_report_instance._mock_db.execute_fetch.call_args
    query_string = args[0]
    query_params = args[1]
    
    assert "SELECT d.user_id, d.username, d.message, d.role, d.timestamp" in query_string
    assert "FROM dialogs d" in query_string
    assert "WHERE d.timestamp >= ?" in query_string # Проверяем условие по времени
    
    # Проверяем, что переданная дата (query_params[0]) - это строка вчерашнего дня в UTC
    moscow_tz = ZoneInfo("Europe/Moscow")
    now_moscow = datetime.now(moscow_tz)
    yesterday_moscow = now_moscow - timedelta(days=1)
    yesterday_utc_expected = yesterday_moscow.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    assert query_params[0] == yesterday_utc_expected
    assert dialogs == mock_dialog_data


def test_format_report_with_dialogs(daily_report_instance: DailyReport):
    # Время должно быть объектом datetime для форматирования
    dialogs_data = [
        (1, "userX", "First message", "user", datetime(2023, 10, 26, 10, 30, 0)),
        (1, "userX", "Bot reply", "assistant", datetime(2023, 10, 26, 10, 31, 0)),
        (2, "userY", "Another question", "user", datetime(2023, 10, 26, 11, 0, 0)),
    ]
    report_html = daily_report_instance.format_report(dialogs_data)

    assert "<h2>Отчет по диалогам за последние 24 часа</h2>" in report_html
    assert "<h3>Диалог с пользователем: userX (ID: 1)</h3>" in report_html
    assert "<p><strong>Пользователь [10:30:00]:</strong> First message</p>" in report_html
    assert "<p><strong>Бот [10:31:00]:</strong> Bot reply</p>" in report_html
    assert "<h3>Диалог с пользователем: userY (ID: 2)</h3>" in report_html
    assert "<p><strong>Пользователь [11:00:00]:</strong> Another question</p>" in report_html

def test_format_report_no_dialogs(daily_report_instance: DailyReport):
    report_html = daily_report_instance.format_report([])
    assert "<p>За последние 24 часа диалогов не было.</p>" in report_html

@pytest.mark.asyncio
async def test_send_daily_report_success(daily_report_instance: DailyReport):
    # Мокаем get_daily_dialogs, чтобы он возвращал какие-то данные
    # Мокаем format_report, чтобы он возвращал простой HTML
    formatted_html_report = "<h1>Test Report</h1>"
    with patch.object(daily_report_instance, 'get_daily_dialogs', AsyncMock(return_value=[(1, "test", "msg", "user", "ts")])) as mock_get_dialogs:
        with patch.object(daily_report_instance, 'format_report', MagicMock(return_value=formatted_html_report)) as mock_format_report:
            
            await daily_report_instance.send_daily_report()

            mock_get_dialogs.assert_called_once()
            mock_format_report.assert_called_once_with(mock_get_dialogs.return_value)
            
            # Проверяем вызов email_service.send_email
            daily_report_instance._mock_email_service.send_email.assert_called_once()
            call_args = daily_report_instance._mock_email_service.send_email.call_args[1] # kwargs
            
            current_date_str = datetime.now().strftime("%Y-%m-%d")
            assert call_args['subject'] == f'Ежедневный отчет по диалогам {current_date_str}'
            assert call_args['body'] == formatted_html_report
            assert call_args['recipient'] is None # Должен использоваться дефолтный из EmailService


@pytest.mark.asyncio
async def test_send_daily_report_exception(daily_report_instance: DailyReport, caplog):
    with patch.object(daily_report_instance, 'get_daily_dialogs', AsyncMock(side_effect=Exception("DB error"))):
        # Отключаем логгер email_service, чтобы он не мешал, если там тоже есть ошибки
        with patch('src.utils.email_service.logger') as mock_email_logger:
            await daily_report_instance.send_daily_report()
            
            # Проверяем, что ошибка была залогирована
            assert "Error sending daily report: DB error" in caplog.text
            daily_report_instance._mock_email_service.send_email.assert_not_called()


def test_schedule_daily_report(daily_report_instance: DailyReport):
    # Используем значения из CONFIG, которые были установлены через os.environ
    expected_hour = CONFIG.REPORT.HOUR
    expected_minute = CONFIG.REPORT.MINUTE

    daily_report_instance.schedule_daily_report() # Вызовет с значениями из .env / CONFIG
    
    daily_report_instance._mock_scheduler.add_job.assert_called_once()
    call_args = daily_report_instance._mock_scheduler.add_job.call_args
    
    assert call_args[0][0] == daily_report_instance.send_daily_report # Первый аргумент - функция
    trigger = call_args[0][1] # Второй аргумент - триггер
    assert hasattr(trigger, 'hour') and trigger.hour == expected_hour
    assert hasattr(trigger, 'minute') and trigger.minute == expected_minute
    assert hasattr(trigger, 'timezone') and str(trigger.timezone) == "Europe/Moscow"
    
    assert call_args[1]['id'] == "daily_report"
    assert call_args[1]['replace_existing'] is True
    
    # Проверяем запуск планировщика, если он не был запущен
    daily_report_instance._mock_scheduler.start.assert_called_once()

def test_schedule_daily_report_custom_time(daily_report_instance: DailyReport):
    custom_hour = 10
    custom_minute = 30
    daily_report_instance._mock_scheduler.reset_mock() # Сбрасываем мок перед новым вызовом

    daily_report_instance.schedule_daily_report(hour=custom_hour, minute=custom_minute)
    
    call_args = daily_report_instance._mock_scheduler.add_job.call_args[0] # args
    trigger = call_args[1]
    assert trigger.hour == custom_hour
    assert trigger.minute == custom_minute

@pytest.mark.asyncio
async def test_main_function(daily_report_instance: DailyReport):
    with patch.object(daily_report_instance, 'send_daily_report', AsyncMock()) as mock_send:
        with patch.object(daily_report_instance, 'schedule_daily_report', MagicMock()) as mock_schedule:
            
            await daily_report_instance.main()
            
            daily_report_instance._mock_db.init_db.assert_called_once()
            mock_send.assert_called_once() # Тестовая отправка
            mock_schedule.assert_called_once() # Планирование


# --- Очистка после тестов ---
def teardown_module(module):
    vars_to_clean = [
        "TELEGRAM_BOT_TOKEN", "OPENAI_API_KEY", "OPENAI_ASSISTANT_ID",
        "SMTP_USER", "SMTP_PASSWORD", "SMTP_SERVER", "SMTP_PORT",
        "SMTP_USERNAME", "SMTP_NOTIFICATION_EMAIL", "REPORT_HOUR", "REPORT_MINUTE",
        "REMINDER_ENABLED"
    ]
    for var in vars_to_clean:
        if var in os.environ:
            del os.environ[var]
