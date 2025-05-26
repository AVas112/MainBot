import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# Загрузка конфигурации и установка переменных окружения
from dotenv import load_dotenv
load_dotenv(override=True)

import os
# Установка переменных для зависимых конфигов, если они не заданы
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake_telegram_token_for_testing")
os.environ.setdefault("OPENAI_API_KEY", "fake_openai_key_for_testing")
os.environ.setdefault("OPENAI_ASSISTANT_ID", "fake_assistant_id_for_testing")
os.environ.setdefault("SMTP_USER", "fake_user")
# ... другие необходимые переменные для CONFIG ...
os.environ.setdefault("REMINDER_ENABLED", "True") # Включаем для тестов сервиса
os.environ.setdefault("REMINDER_FIRST_REMINDER_TIME", "10") # минуты
os.environ.setdefault("REMINDER_SECOND_REMINDER_TIME", "20") # минуты
os.environ.setdefault("REMINDER_FIRST_REMINDER_PROMPT", "Hey, it's been {minutes} minutes!")
os.environ.setdefault("REMINDER_SECOND_REMINDER_PROMPT", "Still there after {minutes} minutes?")

from src.config.config import CONFIG
from src.reminder_service import ReminderService
# Импорты для моков типов
from src.telegram_bot import TelegramBot 
from src.database import Database
from src.chatgpt_assistant import ChatGPTAssistant


# --- Фикстуры ---

@pytest.fixture
def mock_telegram_bot_for_reminder():
    bot = MagicMock(spec=TelegramBot)
    bot.threads = {"123": "thread_123", "456": "thread_456"}
    bot.usernames = {123: "user123", 456: "user456"}
    bot.bot = AsyncMock() # Для bot.send_message
    bot.bot.send_message = AsyncMock()
    return bot

@pytest.fixture
def mock_db_for_reminder():
    db = AsyncMock(spec=Database)
    db.get_users_for_first_reminder = AsyncMock(return_value=[])
    db.get_users_for_second_reminder = AsyncMock(return_value=[])
    db.is_successful_dialog = AsyncMock(return_value=False)
    db.mark_first_reminder_sent = AsyncMock()
    db.mark_second_reminder_sent = AsyncMock()
    db.save_message = AsyncMock()
    return db

@pytest.fixture
def mock_chatgpt_assistant_for_reminder():
    assistant = AsyncMock(spec=ChatGPTAssistant)
    assistant.get_response = AsyncMock(return_value="Generated reminder message.")
    return assistant

@pytest.fixture
def reminder_service_instance(
    mock_telegram_bot_for_reminder, 
    mock_db_for_reminder, 
    mock_chatgpt_assistant_for_reminder
):
    # Убедимся, что CONFIG.REMINDER загружен
    assert CONFIG.REMINDER.ENABLED is not None
    assert CONFIG.REMINDER.FIRST_REMINDER_TIME is not None
    
    service = ReminderService(
        telegram_bot=mock_telegram_bot_for_reminder,
        db=mock_db_for_reminder,
        chatgpt_assistant=mock_chatgpt_assistant_for_reminder
    )
    # Сохраняем моки для легкого доступа в тестах
    service._mock_bot = mock_telegram_bot_for_reminder
    service._mock_db = mock_db_for_reminder
    service._mock_assistant = mock_chatgpt_assistant_for_reminder
    return service

# --- Тесты ---

@pytest.mark.asyncio
@patch('asyncio.create_task') # Мокаем создание задачи
async def test_start_service_enabled(mock_create_task, reminder_service_instance: ReminderService):
    CONFIG.REMINDER.ENABLED = True # Убедимся, что включено
    reminder_service_instance.is_running = False # Сбрасываем состояние

    await reminder_service_instance.start()
    
    assert reminder_service_instance.is_running is True
    mock_create_task.assert_called_once()
    # Можно проверить, что _check_inactive_users_loop была передана в create_task
    assert mock_create_task.call_args[0][0].__name__ == '_check_inactive_users_loop'
    assert reminder_service_instance.task is mock_create_task.return_value

@pytest.mark.asyncio
@patch('asyncio.create_task')
async def test_start_service_disabled(mock_create_task, reminder_service_instance: ReminderService):
    CONFIG.REMINDER.ENABLED = False # Отключаем
    reminder_service_instance.is_running = False

    await reminder_service_instance.start()
    
    assert reminder_service_instance.is_running is False
    mock_create_task.assert_not_called()

@pytest.mark.asyncio
async def test_start_service_already_running(reminder_service_instance: ReminderService):
    CONFIG.REMINDER.ENABLED = True
    reminder_service_instance.is_running = True # Уже запущен
    reminder_service_instance.task = MagicMock() # Уже есть задача
    
    with patch('asyncio.create_task') as mock_create_task:
        await reminder_service_instance.start()
        mock_create_task.assert_not_called() # Не должен запускать новую задачу

@pytest.mark.asyncio
async def test_stop_service(reminder_service_instance: ReminderService):
    reminder_service_instance.is_running = True
    mock_task = AsyncMock() # Используем AsyncMock, чтобы можно было await на cancel
    mock_task.cancel = MagicMock()
    reminder_service_instance.task = mock_task

    await reminder_service_instance.stop()

    assert reminder_service_instance.is_running is False
    mock_task.cancel.assert_called_once()
    # Проверяем, что ожидали завершения задачи
    # В реальном коде suppress(asyncio.CancelledError) и await self.task
    # Для мока достаточно проверить, что cancel был вызван.
    # Если бы task был реальной задачей, можно было бы проверить mock_task.done() или mock_task.cancelled()
    # В данном случае, так как мы мокаем cancel, этого достаточно.

@pytest.mark.asyncio
@patch('asyncio.sleep', new_callable=AsyncMock) # Мокаем sleep, чтобы цикл не ждал
async def test_check_inactive_users_loop_runs_and_calls_check(
    mock_sleep, reminder_service_instance: ReminderService
):
    # Запускаем цикл на одну итерацию
    # Мокаем _check_and_send_reminders, чтобы проверить его вызов
    with patch.object(reminder_service_instance, '_check_and_send_reminders', new_callable=AsyncMock) as mock_check_send:
        
        # Имитируем запуск сервиса и одну итерацию цикла
        reminder_service_instance.is_running = True
        
        # Чтобы выйти из цикла while self.is_running после одной итерации,
        # _check_and_send_reminders может установить is_running = False
        async def side_effect_check_send():
            reminder_service_instance.is_running = False # Останавливаем цикл после первого вызова
        mock_check_send.side_effect = side_effect_check_send

        await reminder_service_instance._check_inactive_users_loop()

        mock_check_send.assert_called_once()
        mock_sleep.assert_called_once_with(reminder_service_instance.check_interval)


@pytest.mark.asyncio
async def test_check_and_send_reminders_flow(reminder_service_instance: ReminderService):
    user_id_first = 123
    user_id_second = 456
    
    reminder_service_instance._mock_db.get_users_for_first_reminder.return_value = [user_id_first]
    reminder_service_instance._mock_db.get_users_for_second_reminder.return_value = [user_id_second]
    
    # Мокаем _send_reminder, чтобы проверить его вызовы
    with patch.object(reminder_service_instance, '_send_reminder', new_callable=AsyncMock) as mock_send_reminder:
        await reminder_service_instance._check_and_send_reminders()

        # Проверяем вызовы для первого напоминания
        reminder_service_instance._mock_db.get_users_for_first_reminder.assert_called_once_with(
            minutes=CONFIG.REMINDER.FIRST_REMINDER_TIME
        )
        reminder_service_instance._mock_db.is_successful_dialog.assert_any_call(user_id=user_id_first)
        mock_send_reminder.assert_any_call(
            user_id=user_id_first,
            reminder_type="first",
            inactive_minutes=CONFIG.REMINDER.FIRST_REMINDER_TIME
        )
        reminder_service_instance._mock_db.mark_first_reminder_sent.assert_called_once_with(user_id_first)

        # Проверяем вызовы для второго напоминания
        reminder_service_instance._mock_db.get_users_for_second_reminder.assert_called_once_with(
            minutes=CONFIG.REMINDER.SECOND_REMINDER_TIME
        )
        reminder_service_instance._mock_db.is_successful_dialog.assert_any_call(user_id=user_id_second)
        mock_send_reminder.assert_any_call(
            user_id=user_id_second,
            reminder_type="second",
            inactive_minutes=CONFIG.REMINDER.SECOND_REMINDER_TIME
        )
        reminder_service_instance._mock_db.mark_second_reminder_sent.assert_called_once_with(user_id_second)

@pytest.mark.asyncio
async def test_check_and_send_reminders_successful_dialog(reminder_service_instance: ReminderService):
    user_id_first = 123
    reminder_service_instance._mock_db.get_users_for_first_reminder.return_value = [user_id_first]
    reminder_service_instance._mock_db.is_successful_dialog.return_value = True # Диалог успешный

    with patch.object(reminder_service_instance, '_send_reminder', new_callable=AsyncMock) as mock_send_reminder:
        await reminder_service_instance._check_and_send_reminders()
        
        reminder_service_instance._mock_db.is_successful_dialog.assert_called_once_with(user_id=user_id_first)
        mock_send_reminder.assert_not_called() # Напоминание не должно отправляться
        reminder_service_instance._mock_db.mark_first_reminder_sent.assert_not_called()


@pytest.mark.asyncio
async def test_send_reminder_first_type(reminder_service_instance: ReminderService):
    user_id = 123
    thread_id = "thread_123"
    inactive_minutes = CONFIG.REMINDER.FIRST_REMINDER_TIME
    expected_prompt = CONFIG.REMINDER.FIRST_REMINDER_PROMPT.format(minutes=inactive_minutes)
    chatgpt_response = "Generated first reminder"

    reminder_service_instance._mock_assistant.get_response.return_value = chatgpt_response

    await reminder_service_instance._send_reminder(user_id, "first", inactive_minutes)

    # Проверка вызова ChatGPT
    reminder_service_instance._mock_assistant.get_response.assert_called_once_with(
        user_message=expected_prompt,
        thread_id=thread_id,
        user_id=str(user_id)
    )
    # Проверка отправки сообщения ботом
    reminder_service_instance._mock_bot.bot.send_message.assert_called_once_with(
        chat_id=user_id,
        text=chatgpt_response,
        parse_mode="HTML"
    )
    # Проверка сохранения сообщения в БД
    reminder_service_instance._mock_db.save_message.assert_called_once_with(
        user_id=user_id,
        username=reminder_service_instance._mock_bot.usernames[user_id],
        message=chatgpt_response,
        role="assistant"
    )

@pytest.mark.asyncio
async def test_send_reminder_second_type(reminder_service_instance: ReminderService):
    user_id = 456 # Другой пользователь для чистоты
    thread_id = "thread_456"
    inactive_minutes = CONFIG.REMINDER.SECOND_REMINDER_TIME
    expected_prompt = CONFIG.REMINDER.SECOND_REMINDER_PROMPT.format(minutes=inactive_minutes)
    chatgpt_response = "Generated second reminder"

    reminder_service_instance._mock_assistant.get_response.return_value = chatgpt_response
    
    await reminder_service_instance._send_reminder(user_id, "second", inactive_minutes)

    reminder_service_instance._mock_assistant.get_response.assert_called_once_with(
        user_message=expected_prompt,
        thread_id=thread_id,
        user_id=str(user_id)
    )
    reminder_service_instance._mock_bot.bot.send_message.assert_called_once_with(
        chat_id=user_id,
        text=chatgpt_response,
        parse_mode="HTML"
    )
    reminder_service_instance._mock_db.save_message.assert_called_once_with(
        user_id=user_id,
        username=reminder_service_instance._mock_bot.usernames[user_id],
        message=chatgpt_response,
        role="assistant"
    )

@pytest.mark.asyncio
async def test_send_reminder_no_thread_id(reminder_service_instance: ReminderService, caplog):
    user_id_no_thread = 999
    # Убедимся, что для этого user_id нет треда в mock_telegram_bot_for_reminder.threads
    assert str(user_id_no_thread) not in reminder_service_instance._mock_bot.threads

    await reminder_service_instance._send_reminder(user_id_no_thread, "first", 10)
    
    assert f"Не найден thread_id для пользователя {user_id_no_thread}" in caplog.text
    reminder_service_instance._mock_assistant.get_response.assert_not_called()
    reminder_service_instance._mock_bot.bot.send_message.assert_not_called()
    reminder_service_instance._mock_db.save_message.assert_not_called()

@pytest.mark.asyncio
async def test_send_reminder_chatgpt_exception(reminder_service_instance: ReminderService, caplog):
    user_id = 123
    reminder_service_instance._mock_assistant.get_response.side_effect = Exception("ChatGPT error")

    await reminder_service_instance._send_reminder(user_id, "first", 10)
    
    assert f"Ошибка при отправке напоминания пользователю {user_id}: ChatGPT error" in caplog.text
    reminder_service_instance._mock_bot.bot.send_message.assert_not_called()
    reminder_service_instance._mock_db.save_message.assert_not_called()


# --- Очистка после тестов ---
def teardown_module(module):
    vars_to_clean = [
        "TELEGRAM_BOT_TOKEN", "OPENAI_API_KEY", "OPENAI_ASSISTANT_ID", "SMTP_USER",
        "REMINDER_ENABLED", "REMINDER_FIRST_REMINDER_TIME", "REMINDER_SECOND_REMINDER_TIME",
        "REMINDER_FIRST_REMINDER_PROMPT", "REMINDER_SECOND_REMINDER_PROMPT"
    ]
    for var in vars_to_clean:
        if var in os.environ:
            del os.environ[var]
