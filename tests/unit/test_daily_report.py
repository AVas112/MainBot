import asyncio
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.daily_report import DailyReport


@pytest.fixture
def mock_db():
    """Фикстура для mock-объекта Database."""
    db_mock = MagicMock()
    db_mock.execute_fetch = AsyncMock()
    return db_mock


@pytest.fixture
def mock_email_service():
    """Фикстура для mock-объекта email_service."""
    email_service_mock = MagicMock()
    email_service_mock.send_email = AsyncMock()
    return email_service_mock


@pytest.fixture
@patch("src.daily_report.Database")
@patch("src.daily_report.email_service")
def daily_report_instance(mock_email_service_ctor, mock_db_ctor, mock_db, mock_email_service):
    """Фикстура для экземпляра DailyReport с mock-зависимостями."""
    mock_db_ctor.return_value = mock_db
    report_instance = DailyReport()
    report_instance.db = mock_db
    return report_instance

@pytest.mark.asyncio
async def test_get_daily_dialogs(daily_report_instance, mock_db):
    """Тест для метода get_daily_dialogs."""
    mock_dialog_data = [
        (1, "user1", "Hello", "user", "2023-01-01 10:00:00"),
        (1, "user1", "Hi bot", "assistant", "2023-01-01 10:01:00"),
        (2, "user2", "Test message", "user", "2023-01-01 11:00:00"),
    ]
    mock_db.execute_fetch.return_value = mock_dialog_data
    dialogs = await daily_report_instance.get_daily_dialogs()
    assert dialogs == mock_dialog_data
    moscow_tz = ZoneInfo("Europe/Moscow")
    now_in_moscow = datetime.now(moscow_tz)
    yesterday_in_moscow = now_in_moscow - timedelta(days=1)
    yesterday_utc = yesterday_in_moscow.astimezone(timezone.utc)
    expected_yesterday_str = yesterday_utc.strftime("%Y-%m-%d %H:%M:%S")
    expected_query = """
            SELECT d.user_id, d.username, d.message, d.role, d.timestamp 
            FROM dialogs d 
            WHERE d.timestamp >= ?
            ORDER BY d.user_id, d.timestamp
        """
    mock_db.execute_fetch.assert_called_once_with(expected_query, (expected_yesterday_str,))

@pytest.mark.asyncio
async def test_get_daily_dialogs_empty(daily_report_instance, mock_db):
    """Тест для get_daily_dialogs, когда нет диалогов."""
    mock_db.execute_fetch.return_value = []
    dialogs = await daily_report_instance.get_daily_dialogs()
    assert dialogs == []
    moscow_tz = ZoneInfo("Europe/Moscow")
    now_in_moscow = datetime.now(moscow_tz)
    yesterday_in_moscow = now_in_moscow - timedelta(days=1)
    yesterday_utc = yesterday_in_moscow.astimezone(timezone.utc)
    expected_yesterday_str = yesterday_utc.strftime("%Y-%m-%d %H:%M:%S")
    expected_query = """
            SELECT d.user_id, d.username, d.message, d.role, d.timestamp 
            FROM dialogs d 
            WHERE d.timestamp >= ?
            ORDER BY d.user_id, d.timestamp
        """
    mock_db.execute_fetch.assert_called_once_with(expected_query, (expected_yesterday_str,))

def test_format_report_empty(daily_report_instance):
    """Тест format_report с пустым списком диалогов."""
    report = daily_report_instance.format_report([])
    assert report == "<p>За последние 24 часа диалогов не было.</p>"

def test_format_report_with_dialogs(daily_report_instance):
    """Тест format_report с данными диалогов."""
    dialogs_data = [
        (1, "user1", "Привет", "user", "2023-01-01 10:00:00"),
        (1, "user1", "Как дела?", "assistant", "2023-01-01 10:01:00"),
        (2, "user2", "Тестовое сообщение", "user", "2023-01-01 11:00:00"),
        (1, "user1", "Все хорошо", "user", "2023-01-01 10:02:00"),
    ]
    report = daily_report_instance.format_report(dialogs_data)
    assert "<h2>Отчет по диалогам за последние 24 часа</h2>" in report
    assert "<h3>Диалог с пользователем: user1 (ID: 1)</h3>" in report
    assert "<p><strong>Пользователь [10:00:00]:</strong> Привет</p>" in report
    assert "<p><strong>Бот [10:01:00]:</strong> Как дела?</p>" in report
    assert "<p><strong>Пользователь [10:02:00]:</strong> Все хорошо</p>" in report 
    assert "<h3>Диалог с пользователем: user2 (ID: 2)</h3>" in report
    assert "<p><strong>Пользователь [11:00:00]:</strong> Тестовое сообщение</p>" in report
    assert report.count("<h3>Диалог с пользователем: user1 (ID: 1)</h3>") == 1
    assert report.count("<h3>Диалог с пользователем: user2 (ID: 2)</h3>") == 1

def test_format_user_dialog_internal_method(daily_report_instance):
    """Тест внутреннего метода _format_user_dialog."""
    messages = [
        {"role": "user", "message": "Первое сообщение", "timestamp": datetime.strptime("2023-01-01 12:00:00", "%Y-%m-%d %H:%M:%S")},
        {"role": "assistant", "message": "Ответ бота", "timestamp": datetime.strptime("2023-01-01 12:01:00", "%Y-%m-%d %H:%M:%S")},
    ]
    formatted_dialog = daily_report_instance._format_user_dialog(123, "testuser", messages)
    assert "<h3>Диалог с пользователем: testuser (ID: 123)</h3>" in formatted_dialog
    assert "<div class='dialog'>" in formatted_dialog
    assert "<p><strong>Пользователь [12:00:00]:</strong> Первое сообщение</p>" in formatted_dialog
    assert "<p><strong>Бот [12:01:00]:</strong> Ответ бота</p>" in formatted_dialog
    assert "</div><hr>" in formatted_dialog

@patch("src.daily_report.datetime")
@patch("src.daily_report.email_service")
@pytest.mark.asyncio
async def test_send_daily_report_success(mock_email_service_patched, mock_datetime, daily_report_instance):
    """Тест успешной отправки ежедневного отчета."""
    mock_now = datetime(2023, 1, 15, 10, 0, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    mock_datetime.now.return_value = mock_now
    daily_report_instance.get_daily_dialogs = AsyncMock(return_value=[(1, "user1", "msg", "user", "ts")])
    daily_report_instance.format_report = MagicMock(return_value="<p>HTML Report</p>")
    await daily_report_instance.send_daily_report()
    daily_report_instance.get_daily_dialogs.assert_called_once()
    daily_report_instance.format_report.assert_called_once_with([(1, "user1", "msg", "user", "ts")])
    expected_subject = f'Ежедневный отчет по диалогам {mock_now.strftime("%Y-%m-%d")}'
    mock_email_service_patched.send_email.assert_called_once_with(
        subject=expected_subject,
        body="<p>HTML Report</p>",
        recipient=None 
    )

@patch("src.daily_report.datetime")
@patch("src.daily_report.email_service")
@pytest.mark.asyncio
async def test_send_daily_report_sends_empty_report(mock_email_service_patched, mock_datetime, daily_report_instance):
    """Тест отправки отчета, когда нет диалогов."""
    mock_now = datetime(2023, 1, 15, 10, 0, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    mock_datetime.now.return_value = mock_now
    daily_report_instance.get_daily_dialogs = AsyncMock(return_value=[])
    expected_html_body = "<p>За последние 24 часа диалогов не было.</p>"
    daily_report_instance.format_report = MagicMock(return_value=expected_html_body)
    await daily_report_instance.send_daily_report()
    daily_report_instance.get_daily_dialogs.assert_called_once()
    daily_report_instance.format_report.assert_called_once_with([])
    expected_subject = f'Ежедневный отчет по диалогам {mock_now.strftime("%Y-%m-%d")}'
    mock_email_service_patched.send_email.assert_called_once_with(
        subject=expected_subject,
        body=expected_html_body,
        recipient=None
    )

@patch("src.daily_report.logger")
@patch("src.daily_report.email_service")
@pytest.mark.asyncio
async def test_send_daily_report_email_failure(mock_email_service_patched, mock_logger, daily_report_instance):
    """Тест обработки ошибки при отправке email в send_daily_report."""
    daily_report_instance.get_daily_dialogs = AsyncMock(return_value=[(1, "user1", "msg", "user", "ts")])
    daily_report_instance.format_report = MagicMock(return_value="<p>HTML Report</p>")
    mock_email_service_patched.send_email.side_effect = Exception("Email send failed")
    await daily_report_instance.send_daily_report()
    assert mock_email_service_patched.send_email.called
    mock_logger.error.assert_called_once()
    args, _ = mock_logger.error.call_args
    assert "Error sending daily report: Email send failed" in args[0]

@patch("src.daily_report.AsyncIOScheduler")
@patch("src.daily_report.CronTrigger")
@patch("os.getenv")
def test_schedule_daily_report_defaults(mock_getenv, mock_cron_trigger, mock_scheduler_constructor, daily_report_instance):
    """Тест schedule_daily_report с использованием значений по умолчанию."""
    mock_getenv.side_effect = lambda key, default: {"REPORT_HOUR": "6", "REPORT_MINUTE": "0"}.get(key, default)
    mock_scheduler_instance = mock_scheduler_constructor.return_value
    mock_scheduler_instance.running = False
    daily_report_instance.scheduler = mock_scheduler_instance
    daily_report_instance.schedule_daily_report()
    mock_scheduler_instance.add_job.assert_called_once()
    args, kwargs = mock_scheduler_instance.add_job.call_args
    assert args[0] == daily_report_instance.send_daily_report
    mock_cron_trigger.assert_called_once_with(hour=6, minute=0, timezone="Europe/Moscow")
    assert args[1] == mock_cron_trigger.return_value
    assert kwargs["id"] == "daily_report"
    assert kwargs["replace_existing"] is True
    mock_scheduler_instance.start.assert_called_once()

@patch("src.daily_report.AsyncIOScheduler")
@patch("src.daily_report.CronTrigger")
@patch("os.getenv")
def test_schedule_daily_report_custom_time(mock_getenv, mock_cron_trigger, mock_scheduler_constructor, daily_report_instance):
    """Тест schedule_daily_report с указанием времени."""
    mock_scheduler_instance = mock_scheduler_constructor.return_value
    mock_scheduler_instance.running = True
    daily_report_instance.scheduler = mock_scheduler_instance
    custom_hour = 10
    custom_minute = 30
    daily_report_instance.schedule_daily_report(hour=custom_hour, minute=custom_minute)
    mock_getenv.assert_not_called()
    mock_scheduler_instance.add_job.assert_called_once()
    args, kwargs = mock_scheduler_instance.add_job.call_args
    assert args[0] == daily_report_instance.send_daily_report
    mock_cron_trigger.assert_called_once_with(hour=custom_hour, minute=custom_minute, timezone="Europe/Moscow")
    assert args[1] == mock_cron_trigger.return_value
    assert kwargs["id"] == "daily_report"
    assert kwargs["replace_existing"] is True
    mock_scheduler_instance.start.assert_not_called()

@patch("src.daily_report.AsyncIOScheduler")
@patch("src.daily_report.CronTrigger")
@patch("os.getenv")
@patch("src.daily_report.logger")
def test_schedule_daily_report_logging(mock_logger, mock_getenv, mock_cron_trigger, mock_scheduler_constructor, daily_report_instance):
    """Тест логирования в schedule_daily_report."""
    mock_getenv.side_effect = lambda key, default: {"REPORT_HOUR": "8", "REPORT_MINUTE": "15"}.get(key, default)
    mock_scheduler_instance = mock_scheduler_constructor.return_value
    mock_scheduler_instance.running = False
    daily_report_instance.scheduler = mock_scheduler_instance
    daily_report_instance.schedule_daily_report()
    mock_logger.info.assert_called()
    expected_log_message = "Scheduler configured to send report at 08:15 (Europe/Moscow)"
    called_with_expected_message = False
    for call_args in mock_logger.info.call_args_list:
        if expected_log_message in call_args[0][0]:
            called_with_expected_message = True
            break
    assert called_with_expected_message, f"Expected log message '{expected_log_message}' not found in logger calls."
