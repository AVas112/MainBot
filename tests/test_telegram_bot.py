import pytest
import pytest_asyncio # Added import
import asyncio
import json
import os
from unittest.mock import MagicMock, AsyncMock, patch, mock_open

# Загрузка конфигурации и установка переменных окружения
from dotenv import load_dotenv
load_dotenv(override=True)

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
os.environ.setdefault("REMINDER_ENABLED", "False") # Отключаем напоминания для этих тестов по умолчанию
# Добавьте другие переменные, если они необходимы для инициализации CONFIG


# Важно: TelegramBot импортирует много модулей, которые зависят от CONFIG.
# Убедимся, что CONFIG загружен корректно перед импортом TelegramBot.
from src.config.config import CONFIG
from src.telegram_bot import TelegramBot
from telegram import Update, User, Message, Chat
from telegram.ext import Application, CallbackContext


# --- Фикстуры ---

@pytest.fixture
def mock_config_values():
    # Эта фикстура может переопределить значения CONFIG для конкретных тестов, если нужно
    # Например, CONFIG.TELEGRAM.ADMIN_CHAT_ID = 12345
    # Но лучше стараться, чтобы .env файл содержал все необходимые тестовые значения
    pass

@pytest_asyncio.fixture # Changed to pytest_asyncio.fixture
async def mock_db():
    db = AsyncMock()
    db.init_db = AsyncMock()
    db.is_user_registered = AsyncMock(return_value=False)
    db.register_user = AsyncMock()
    db.save_message = AsyncMock()
    db.get_dialog = AsyncMock(return_value=["User: test", "Assistant: reply"])
    # Добавьте другие моки методов БД по мере необходимости
    return db

@pytest.fixture
def mock_chatgpt_assistant():
    assistant = AsyncMock()
    assistant.create_thread = MagicMock(return_value="new_thread_123")
    assistant.get_response = AsyncMock(return_value="Mocked ChatGPT response")
    return assistant

@pytest.fixture
def mock_daily_report():
    report = AsyncMock()
    report.main = AsyncMock() # Используется в initialize
    return report

@pytest.fixture
def mock_reminder_service():
    service = AsyncMock()
    service.start = AsyncMock() # Используется в initialize
    return service

@pytest.fixture
def mock_email_service():
    # Мокаем глобальный email_service, который импортируется в telegram_bot.py
    with patch('src.telegram_bot.email_service', new_callable=AsyncMock) as mock_es:
        mock_es.send_telegram_dialog_email = AsyncMock()
        yield mock_es


@pytest_asyncio.fixture # Changed to pytest_asyncio.fixture
@patch('telegram.ext.Application.builder')
@patch('src.telegram_bot.Database')
@patch('src.telegram_bot.ChatGPTAssistant')
@patch('src.telegram_bot.DailyReport')
@patch('src.telegram_bot.ReminderService')
@patch('src.telegram_bot.notify_admin_about_new_dialog', new_callable=AsyncMock) # Мокаем импортированную функцию
async def bot_instance(
    mock_notify_admin_func, # Этот мок должен быть первым, если он для импортированного объекта
    MockReminderService, MockDailyReport, MockChatGPTAssistant, MockDatabase, mock_app_builder,
    mock_db, mock_chatgpt_assistant, mock_daily_report, mock_reminder_service, mock_email_service # фикстуры с моками
):
    # Настраиваем моки классов, чтобы они возвращали наши фикстуры-моки
    MockDatabase.return_value = mock_db
    MockChatGPTAssistant.return_value = mock_chatgpt_assistant
    MockDailyReport.return_value = mock_daily_report
    MockReminderService.return_value = mock_reminder_service

    # Настройка Application.builder()
    mock_app = MagicMock(spec=Application)
    mock_app.bot = AsyncMock() # mock_app.bot должен быть AsyncMock для await bot.send_message
    mock_app_builder.return_value.token.return_value.build.return_value = mock_app
    
    # Мокаем load_threads, чтобы он возвращал пустой словарь по умолчанию
    with patch.object(TelegramBot, 'load_threads', return_value={}) as mock_load_threads:
        with patch.object(TelegramBot, 'save_threads', MagicMock()) as mock_save_threads:
            # Убедимся, что TOKEN загружен
            assert CONFIG.TELEGRAM.BOT_TOKEN is not None, "Telegram bot token not configured for tests"
            
            # Создаем экземпляр бота. Он вызовет конструкторы мокнутых классов.
            bot = TelegramBot()
            # Явно присваиваем моки, если конструктор TelegramBot их не так устанавливает
            bot.db = mock_db
            bot.chatgpt_assistant = mock_chatgpt_assistant
            bot.daily_report = mock_daily_report # Будет переопределен в initialize
            bot.reminder_service = mock_reminder_service # Будет переопределен в initialize
            bot.application = mock_app # Присваиваем мок приложения
            bot.bot = mock_app.bot # Присваиваем мок бота
            
            # Сохраняем моки для ассертов в тестах
            bot._mock_app = mock_app
            bot._mock_load_threads = mock_load_threads
            bot._mock_save_threads = mock_save_threads
            bot._mock_notify_admin_func = mock_notify_admin_func
            
            # Вызываем асинхронную инициализацию
            # В `initialize` создаются новые экземпляры DailyReport и ReminderService,
            # поэтому нам нужно, чтобы наши моки классов возвращали правильные инстансы
            await bot.initialize()
            
            # Проверяем, что DailyReport и ReminderService были переинициализированы с моками
            assert bot.daily_report is mock_daily_report
            mock_daily_report.main.assert_called_once()
            assert bot.reminder_service is mock_reminder_service
            mock_reminder_service.start.assert_called_once()
            
            return bot


# --- Тесты ---

@pytest.mark.asyncio
async def test_bot_initialization(bot_instance: TelegramBot, mock_db):
    assert bot_instance.token == CONFIG.TELEGRAM.BOT_TOKEN
    assert bot_instance.application is not None
    assert bot_instance.bot is not None
    mock_db.init_db.assert_called_once()
    bot_instance._mock_load_threads.assert_called_once()

@pytest.mark.asyncio
async def test_start_command(bot_instance: TelegramBot):
    update = AsyncMock(spec=Update)
    update.effective_user = User(id=123, first_name="Test", is_bot=False)
    update.message = AsyncMock(spec=Message)
    update.message.reply_text = AsyncMock()

    await bot_instance.start(update, None)
    update.message.reply_text.assert_called_once_with(
        text="Good day, this is Coliving. To continue the dialogue, please tell us briefly about yourself."
    )

@pytest.mark.asyncio
async def test_help_command(bot_instance: TelegramBot):
    update = AsyncMock(spec=Update)
    update.effective_user = User(id=123, first_name="Test", is_bot=False)
    update.message = AsyncMock(spec=Message)
    update.message.reply_text = AsyncMock()

    await bot_instance.help(update, None)
    help_text = "Available commands:\n/start - Start dialog\n/help - Show this message\n"
    update.message.reply_text.assert_called_once_with(text=help_text)

@pytest.mark.asyncio
async def test_handle_message_new_user_new_thread(
    bot_instance: TelegramBot, mock_db, mock_chatgpt_assistant
):
    user_id = 789
    username = "newbie"
    message_text = "Hello, I am new"
    
    update = AsyncMock(spec=Update)
    update.effective_user = User(id=user_id, first_name=username, is_bot=False, username=username)
    # update.message.date нужен для register_user
    update.message = AsyncMock(spec=Message, text=message_text, date=datetime.now(timezone.utc))
    update.message.reply_text = AsyncMock()

    mock_db.is_user_registered.return_value = False # Новый пользователь
    bot_instance.threads = {} # Нет существующих тредов

    await bot_instance.handle_message(update, None)

    # Проверка регистрации пользователя
    mock_db.is_user_registered.assert_called_once_with(user_id)
    mock_db.register_user.assert_called_once()
    # Проверка вызова notify_admin_about_new_dialog (мокнутая функция)
    bot_instance._mock_notify_admin_func.assert_called_once_with(bot_instance.bot, user_id, username)

    # Проверка сохранения сообщения пользователя
    mock_db.save_message.assert_any_call(
        user_id=user_id, username=username, message=message_text, role="user"
    )
    
    # Проверка создания нового треда
    mock_chatgpt_assistant.create_thread.assert_called_once_with(user_id=user_id)
    assert str(user_id) in bot_instance.threads
    assert bot_instance.threads[str(user_id)] == "new_thread_123"
    bot_instance._mock_save_threads.assert_called_once() # Проверка сохранения тредов

    # Проверка вызова ChatGPT
    mock_chatgpt_assistant.get_response.assert_called_once_with(
        user_message=message_text,
        thread_id="new_thread_123",
        user_id=str(user_id)
    )

    # Проверка сохранения ответа ассистента
    mock_db.save_message.assert_any_call(
        user_id=user_id, username=username, message="Mocked ChatGPT response", role="assistant"
    )

    # Проверка ответа пользователю
    update.message.reply_text.assert_called_once_with(
        text="Mocked ChatGPT response", parse_mode="HTML"
    )
    assert bot_instance.dialogs[user_id][-1] == "ChatGPT: Mocked ChatGPT response"

@pytest.mark.asyncio
async def test_handle_message_existing_user_existing_thread(
    bot_instance: TelegramBot, mock_db, mock_chatgpt_assistant
):
    user_id = 555
    username = "regular"
    message_text = "Another message"
    thread_id_existing = "thread_abc"

    update = AsyncMock(spec=Update)
    update.effective_user = User(id=user_id, first_name=username, is_bot=False, username=username)
    update.message = AsyncMock(spec=Message, text=message_text, date=datetime.now(timezone.utc))
    update.message.reply_text = AsyncMock()

    mock_db.is_user_registered.return_value = True # Существующий пользователь
    bot_instance.threads = {str(user_id): thread_id_existing} # Существующий тред
    bot_instance.dialogs[user_id] = ["User: Previous message"] # Существующий диалог

    await bot_instance.handle_message(update, None)

    mock_db.register_user.assert_not_called() # Не должен регистрировать снова
    bot_instance._mock_notify_admin_func.assert_not_called() # Не должен уведомлять снова
    mock_chatgpt_assistant.create_thread.assert_not_called() # Не должен создавать тред
    bot_instance._mock_save_threads.assert_not_called() # Не должен сохранять треды (если не было изменений)

    mock_chatgpt_assistant.get_response.assert_called_once_with(
        user_message=message_text,
        thread_id=thread_id_existing,
        user_id=str(user_id)
    )
    update.message.reply_text.assert_called_once_with(text="Mocked ChatGPT response", parse_mode="HTML")
    assert bot_instance.dialogs[user_id][-1] == "ChatGPT: Mocked ChatGPT response"


@pytest.mark.asyncio
async def test_handle_message_chatgpt_error(bot_instance: TelegramBot, mock_chatgpt_assistant):
    user_id = 666
    message_text = "Trigger error"
    update = AsyncMock(spec=Update)
    update.effective_user = User(id=user_id, first_name="ErrorUser", is_bot=False, username="erroruser")
    update.message = AsyncMock(spec=Message, text=message_text, date=datetime.now(timezone.utc))
    update.message.reply_text = AsyncMock()

    bot_instance.threads = {str(user_id): "thread_error"}
    error_message = "ChatGPT API is down"
    mock_chatgpt_assistant.get_response.side_effect = Exception(error_message)

    await bot_instance.handle_message(update, None)

    update.message.reply_text.assert_called_once_with(
        text=f"An error occurred while processing your message: {error_message}"
    )

def test_load_threads_file_exists():
    # Мокаем os.path.exists и open
    with patch('os.path.exists', return_value=True):
        mock_file_content = json.dumps({"123": "thread_a", "456": "thread_b"})
        with patch('builtins.open', mock_open(read_data=mock_file_content)) as mock_file:
            # Создаем временный экземпляр бота только для этого теста, не используя фикстуру
            # так как нам нужно контролировать вызов load_threads в конструкторе
            with patch('telegram.ext.Application.builder'): # Мок для Application
                bot = TelegramBot() 
            loaded = bot.threads # load_threads вызывается в __init__
            assert loaded == {"123": "thread_a", "456": "thread_b"}
            mock_file.assert_called_once_with("threads.json")

def test_load_threads_file_not_exists():
    with patch('os.path.exists', return_value=False):
        with patch('telegram.ext.Application.builder'):
            bot = TelegramBot()
        loaded = bot.threads
        assert loaded == {}

def test_load_threads_invalid_json():
    with patch('os.path.exists', return_value=True):
        with patch('builtins.open', mock_open(read_data="invalid json")) as mock_file:
            with patch('telegram.ext.Application.builder'):
                bot = TelegramBot()
            loaded = bot.threads
            assert loaded == {} # Должен вернуть пустой словарь при ошибке декодирования

def test_save_threads(bot_instance: TelegramBot): # Используем фикстуру, где save_threads уже мокнут
    bot_instance.threads = {"789": "thread_c"}
    # В фикстуре bot_instance, save_threads уже заменен на MagicMock.
    # Здесь мы просто вызываем его и проверяем, что он был вызван.
    # Если бы мы хотели проверить запись в файл, мок был бы сложнее.
    
    # Для проверки фактической записи, если бы save_threads не был мокнут в фикстуре:
    # bot_instance._mock_save_threads.reset_mock() # Сбрасываем мок из фикстуры
    # with patch('builtins.open', mock_open()) as mock_file_open:
    #     with patch('json.dump') as mock_json_dump:
    #         bot_instance.threads = {"789": "thread_c"}
    #         bot_instance.save_threads() # Вызываем реальный метод
    #         mock_file_open.assert_called_once_with("threads.json", "w")
    #         mock_json_dump.assert_called_once()
    #         # Первый аргумент json.dump - это self.threads
    #         assert mock_json_dump.call_args[0][0] == {"789": "thread_c"}
    
    # Так как в фикстуре save_threads уже мокнут, мы просто его вызываем
    bot_instance.save_threads()
    bot_instance._mock_save_threads.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_method(bot_instance: TelegramBot, mock_email_service, mock_db):
    user_id = 101
    username = "email_user"
    contact_info = {"name": "Email Test"}
    dialog_text_from_db = ["User: Email dialog", "Assistant: Roger that"]

    bot_instance.usernames[user_id] = username
    mock_db.get_dialog.return_value = dialog_text_from_db

    await bot_instance.send_email(user_id=user_id, contact_info=contact_info)

    mock_db.get_dialog.assert_called_once_with(user_id)
    mock_email_service.send_telegram_dialog_email.assert_called_once_with(
        user_id=user_id,
        username=f"@{username}", # Проверяем добавление @
        contact_info=contact_info,
        dialog_text=dialog_text_from_db
    )

# Пример теста для run, если это необходимо (обычно не тестируется напрямую, т.к. это точка входа)
# def test_run_method_setup(bot_instance: TelegramBot):
#     bot_instance.run() # run - это блокирующий вызов, его сложно тестировать так
#     # Вместо этого мы проверяем, что хендлеры добавлены
#     assert len(bot_instance.application.add_handler.call_args_list) == 3 # start, help, message
#     # Проверить, что run_polling вызван, если Application - это мок
#     bot_instance._mock_app.run_polling.assert_called_once()


# --- Очистка после тестов ---
def teardown_module(module):
    # Удаление переменных окружения, установленных для тестов
    vars_to_clean = [
        "TELEGRAM_BOT_TOKEN", "OPENAI_API_KEY", "OPENAI_ASSISTANT_ID",
        "SMTP_USER", "SMTP_PASSWORD", "SMTP_SERVER", "SMTP_PORT",
        "SMTP_USERNAME", "SMTP_NOTIFICATION_EMAIL", "REMINDER_ENABLED"
    ]
    for var in vars_to_clean:
        if var in os.environ:
            del os.environ[var]
    # Удаляем threads.json, если он был создан в каких-то тестах (хотя мы его мокаем)
    if os.path.exists("threads.json"):
        os.remove("threads.json")

# Необходимы datetime и timezone из datetime для update.message.date
from datetime import datetime, timezone
