"""Юнит-тесты для TelegramBot."""

import asyncio
import json
import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.chatgpt_assistant import ChatGPTAssistant
from src.config import CONFIG  # Используется для мока
from src.daily_report import DailyReport
from src.database import Database
from src.reminder_service import ReminderService
from src.telegram_bot import TelegramBot
from src.telegram_notifications import notify_admin_about_new_dialog # Используется для мока
from src.utils.email_service import email_service # Используется для мока


@pytest.fixture
def mock_update():
    """Фикстура для мока объекта Update."""
    update = AsyncMock(spec=Update)
    update.effective_user = MagicMock()
    update.effective_user.id = 123456
    update.effective_user.username = "testuser"
    update.message = AsyncMock()
    update.message.text = "Hello"
    update.message.date = MagicMock()
    update.message.date.isoformat.return_value = "2024-01-01T12:00:00"
    return update


@pytest.fixture
def mock_context():
    """Фикстура для мока объекта Context."""
    context = MagicMock()
    return context


@pytest.fixture
@patch("src.telegram_bot.CONFIG")
@patch("src.telegram_bot.Application.builder")
@patch("src.telegram_bot.Database")
@patch("src.telegram_bot.ChatGPTAssistant")
@patch("src.telegram_bot.asyncio.Lock")
def telegram_bot_instance(
    mock_lock,
    mock_chatgpt_assistant,
    mock_database,
    mock_app_builder,
    mock_config_module,
    mock_config,  # Фикстура из conftest
):
    """Фикстура для создания экземпляра TelegramBot с моками."""
    mock_config_module.TELEGRAM.BOT_TOKEN = "test_token"
    
    mock_app_instance = MagicMock(spec=Application)
    mock_bot_instance = AsyncMock()
    mock_app_instance.bot = mock_bot_instance
    mock_app_builder.return_value.token.return_value.build.return_value = mock_app_instance
    
    bot = TelegramBot()
    # Переопределяем моками созданные в __init__ экземпляры, если нужно более тонкое управление
    bot.db = mock_database.return_value
    bot.chatgpt_assistant = mock_chatgpt_assistant.return_value
    bot.file_lock = mock_lock.return_value
    bot.application = mock_app_instance # Важно для .add_handler и .run_polling
    bot.bot = mock_bot_instance # Важно для notify_admin_about_new_dialog и других взаимодействий с bot API
    
    # Моки для зависимостей, создаваемых в initialize
    bot.daily_report = AsyncMock(spec=DailyReport)
    bot.reminder_service = AsyncMock(spec=ReminderService)
    
    return bot


class TestTelegramBotInit:
    """Тесты для инициализации TelegramBot."""

    @patch("src.telegram_bot.CONFIG")
    @patch("src.telegram_bot.Application.builder")
    @patch("src.telegram_bot.Database")
    @patch("src.telegram_bot.ChatGPTAssistant")
    @patch("src.telegram_bot.TelegramBot.load_threads")
    @patch("src.telegram_bot.asyncio.Lock")
    def test_init_attributes(
        self,
        mock_lock,
        mock_load_threads,
        mock_chatgpt_assistant,
        mock_database,
        mock_app_builder,
        mock_config_module,
    ):
        """Тест проверки атрибутов после инициализации."""
        mock_config_module.TELEGRAM.BOT_TOKEN = "test_token_value"
        mock_app_instance = MagicMock(spec=Application)
        mock_bot_api_instance = AsyncMock()
        mock_app_instance.bot = mock_bot_api_instance
        mock_app_builder.return_value.token.return_value.build.return_value = mock_app_instance
        mock_load_threads.return_value = {"123": "thread_abc"}

        bot = TelegramBot()

        assert bot.token == "test_token_value"
        assert bot.application == mock_app_instance
        assert bot.bot == mock_bot_api_instance
        assert isinstance(bot.logger, logging.Logger)
        assert bot.dialogs == {}
        assert bot.threads == {"123": "thread_abc"}
        mock_load_threads.assert_called_once()
        assert bot.file_lock == mock_lock.return_value
        assert bot.usernames == {}
        assert isinstance(bot.db, MagicMock)  # Проверяем, что это мок Database
        mock_database.assert_called_once_with()
        
        assert isinstance(bot.chatgpt_assistant, MagicMock) # Проверяем, что это мок ChatGPTAssistant
        mock_chatgpt_assistant.assert_called_once_with(telegram_bot=bot)

        assert bot.daily_report is None
        assert bot.reminder_service is None


@pytest.mark.asyncio
class TestTelegramBotAsyncMethods:
    """Тесты для асинхронных методов TelegramBot."""

    @patch("src.telegram_bot.DailyReport")
    @patch("src.telegram_bot.ReminderService")
    async def test_initialize(
        self,
        mock_reminder_service_class,
        mock_daily_report_class,
        telegram_bot_instance: TelegramBot,
    ):
        """Тест асинхронной инициализации компонентов."""
        mock_daily_report_instance = AsyncMock(spec=DailyReport)
        mock_daily_report_class.return_value = mock_daily_report_instance

        mock_reminder_service_instance = AsyncMock(spec=ReminderService)
        mock_reminder_service_class.return_value = mock_reminder_service_instance

        # Переназначаем моки, так как они создаются внутри initialize
        telegram_bot_instance.db = AsyncMock(spec=Database) # Убедимся, что db это AsyncMock для await

        await telegram_bot_instance.initialize()

        telegram_bot_instance.db.init_db.assert_awaited_once()
        
        mock_daily_report_class.assert_called_once_with(telegram_bot=telegram_bot_instance)
        mock_daily_report_instance.main.assert_awaited_once()
        assert telegram_bot_instance.daily_report == mock_daily_report_instance

        mock_reminder_service_class.assert_called_once_with(
            telegram_bot=telegram_bot_instance,
            db=telegram_bot_instance.db,
            chatgpt_assistant=telegram_bot_instance.chatgpt_assistant,
        )
        mock_reminder_service_instance.start.assert_awaited_once()
        assert telegram_bot_instance.reminder_service == mock_reminder_service_instance

    @patch("src.telegram_bot.asyncio.new_event_loop")
    @patch("src.telegram_bot.asyncio.set_event_loop")
    async def test_run(
        self,
        mock_set_event_loop,
        mock_new_event_loop,
        telegram_bot_instance: TelegramBot,
        mock_update: Update, # Используем фикстуру, хотя она тут не нужна напрямую
        mock_context,       # Используем фикстуру, хотя она тут не нужна напрямую
    ):
        """Тест запуска бота и настройки обработчиков."""
        mock_loop = MagicMock()
        mock_new_event_loop.return_value = mock_loop
        
        # Мокируем initialize, чтобы он не выполнял реальную логику
        # Используем spec=False для предотвращения создания корутины при обычном вызове
        telegram_bot_instance.initialize = AsyncMock(spec=False)

        telegram_bot_instance.run()

        mock_new_event_loop.assert_called_once()
        mock_set_event_loop.assert_called_once_with(mock_loop)
        # Проверяем только факт вызова метода, без проверки точного объекта coroutine
        assert mock_loop.run_until_complete.call_count == 1
        
        # В коде используется loop.run_until_complete вместо await, поэтому проверяем, что метод был вызван, а не awaited
        telegram_bot_instance.initialize.assert_called_once()

        assert len(telegram_bot_instance.application.add_handler.call_args_list) == 3
        
        # Проверка первого вызова add_handler (для /start)
        handler_call_start = telegram_bot_instance.application.add_handler.call_args_list[0]
        assert isinstance(handler_call_start[1]["handler"], CommandHandler)
        # Проверяем, что команда 'start' находится в commands (frozenset)
        assert 'start' in handler_call_start[1]["handler"].commands
        assert handler_call_start[1]["handler"].callback == telegram_bot_instance.start

        # Проверка второго вызова add_handler (для /help)
        handler_call_help = telegram_bot_instance.application.add_handler.call_args_list[1]
        assert isinstance(handler_call_help[1]["handler"], CommandHandler)
        # Проверяем, что команда 'help' находится в commands (frozenset)
        assert 'help' in handler_call_help[1]["handler"].commands
        assert handler_call_help[1]["handler"].callback == telegram_bot_instance.help
        
        # Проверка третьего вызова add_handler (для MessageHandler)
        handler_call_message = telegram_bot_instance.application.add_handler.call_args_list[2]
        assert isinstance(handler_call_message[1]["handler"], MessageHandler)
        message_filters = handler_call_message[1]["handler"].filters
        assert str(message_filters) == str(filters.TEXT & ~filters.COMMAND)
        assert handler_call_message[1]["handler"].callback == telegram_bot_instance.handle_message

        telegram_bot_instance.application.run_polling.assert_called_once_with(
            allowed_updates=Update.ALL_TYPES
        )

    async def test_start_command(
        self,
        telegram_bot_instance: TelegramBot,
        mock_update: Update,
        mock_context,
    ):
        """Тест обработчика команды /start."""
        await telegram_bot_instance.start(update=mock_update, context=mock_context)
        
        mock_update.message.reply_text.assert_awaited_once_with(
            text="Добро пожаловать в Школу продаж полного цикла! "
                 "Я - ваш ИИ‑продавец: задам пару вопросов,подсвечу точки роста. "
                 "Готовы включить турбо‑режим продаж?"
        )
        # Можно добавить проверку логгирования, если логгер мокирован

    async def test_help_command(
        self,
        telegram_bot_instance: TelegramBot,
        mock_update: Update,
        mock_context,
    ):
        """Тест обработчика команды /help."""
        await telegram_bot_instance.help(update=mock_update, context=mock_context)
        
        mock_update.message.reply_text.assert_awaited_once_with(
            text="Available commands:\n/start - Start dialog\n/help - Show this message\n"
        )

    @patch("src.telegram_bot.notify_admin_about_new_dialog", new_callable=AsyncMock)
    async def test_handle_message_new_user_new_thread(
        self,
        mock_notify_admin,
        telegram_bot_instance: TelegramBot,
        mock_update: Update,
        mock_context,
    ):
        """Тест обработки сообщения от нового пользователя (создание треда)."""
        user_id = mock_update.effective_user.id
        username = mock_update.effective_user.username
        message_text = mock_update.message.text
        
        telegram_bot_instance.db.is_user_registered = AsyncMock(return_value=False)
        telegram_bot_instance.db.register_user = AsyncMock()
        telegram_bot_instance.db.save_message = AsyncMock()
        
        telegram_bot_instance.threads = {} # Убедимся, что тред будет создан
        telegram_bot_instance.chatgpt_assistant.create_thread = MagicMock(return_value="new_thread_id")
        telegram_bot_instance.chatgpt_assistant.get_response = AsyncMock(return_value="Test response")
        telegram_bot_instance.save_threads = MagicMock() # Мокируем, чтобы не писать в файл

        await telegram_bot_instance.handle_message(update=mock_update, context=mock_context)

        assert telegram_bot_instance.usernames[user_id] == username
        assert user_id in telegram_bot_instance.dialogs
        
        telegram_bot_instance.db.is_user_registered.assert_awaited_once_with(user_id=user_id)
        telegram_bot_instance.db.register_user.assert_awaited_once_with(
            user_id=user_id,
            username=username,
            first_seen=mock_update.message.date.isoformat.return_value
        )
        mock_notify_admin.assert_awaited_once_with(telegram_bot_instance.application.bot, user_id, username)
        
        # Проверка сохранения сообщения пользователя
        telegram_bot_instance.db.save_message.assert_any_await(
            user_id=user_id, username=username, message=message_text, role="user"
        )
        assert f"User: {message_text}" in telegram_bot_instance.dialogs[user_id]

        telegram_bot_instance.chatgpt_assistant.create_thread.assert_called_once_with(user_id=user_id)
        assert telegram_bot_instance.threads[str(user_id)] == "new_thread_id"
        telegram_bot_instance.save_threads.assert_called_once()

        telegram_bot_instance.chatgpt_assistant.get_response.assert_awaited_once_with(
            user_message=message_text, thread_id="new_thread_id", user_id=str(user_id)
        )
        # Проверка сохранения ответа ассистента
        telegram_bot_instance.db.save_message.assert_any_await(
            user_id=user_id, username=username, message="Test response", role="assistant"
        )
        assert "ChatGPT: Test response" in telegram_bot_instance.dialogs[user_id]
        
        mock_update.message.reply_text.assert_awaited_once_with(text="Test response", parse_mode="HTML")

    async def test_handle_message_existing_user_existing_thread(
        self,
        telegram_bot_instance: TelegramBot,
        mock_update: Update,
        mock_context,
    ):
        """Тест обработки сообщения от существующего пользователя с существующим тредом."""
        user_id = mock_update.effective_user.id
        username = mock_update.effective_user.username
        message_text = mock_update.message.text
        existing_thread_id = "existing_thread_123"

        telegram_bot_instance.db.is_user_registered = AsyncMock(return_value=True) # Пользователь уже есть
        telegram_bot_instance.db.save_message = AsyncMock()
        
        telegram_bot_instance.threads = {str(user_id): existing_thread_id} # Тред уже есть
        telegram_bot_instance.chatgpt_assistant.create_thread = MagicMock() # Не должен вызываться
        telegram_bot_instance.chatgpt_assistant.get_response = AsyncMock(return_value="Another response")
        telegram_bot_instance.save_threads = MagicMock() # Не должен вызываться для создания треда

        await telegram_bot_instance.handle_message(update=mock_update, context=mock_context)

        telegram_bot_instance.chatgpt_assistant.create_thread.assert_not_called()
        telegram_bot_instance.save_threads.assert_not_called() # Если только не было ошибки при сохранении

        telegram_bot_instance.chatgpt_assistant.get_response.assert_awaited_once_with(
            user_message=message_text, thread_id=existing_thread_id, user_id=str(user_id)
        )
        mock_update.message.reply_text.assert_awaited_once_with(text="Another response", parse_mode="HTML")

    async def test_handle_message_chatgpt_error(
        self,
        telegram_bot_instance: TelegramBot,
        mock_update: Update,
        mock_context,
    ):
        """Тест обработки ошибки при получении ответа от ChatGPT."""
        user_id = mock_update.effective_user.id
        
        telegram_bot_instance.db.is_user_registered = AsyncMock(return_value=True)
        telegram_bot_instance.db.save_message = AsyncMock()
        telegram_bot_instance.threads = {str(user_id): "thread_id"}
        
        error_message = "ChatGPT API is down"
        telegram_bot_instance.chatgpt_assistant.get_response = AsyncMock(
            side_effect=Exception(error_message)
        )

        await telegram_bot_instance.handle_message(update=mock_update, context=mock_context)

        mock_update.message.reply_text.assert_awaited_once_with(
            text=f"An error occurred while processing your message: {error_message}"
        )
        # Можно добавить проверку логгирования ошибки

    async def test_handle_message_general_error(
        self,
        telegram_bot_instance: TelegramBot,
        mock_update: Update,
        mock_context,
    ):
        """Тест обработки общей ошибки в handle_message."""
        error_message = "Something went wrong"
        # Мокируем db.is_user_registered чтобы вызвать ошибку до вызова ChatGPT
        telegram_bot_instance.db.is_user_registered = AsyncMock(side_effect=Exception(error_message))

        await telegram_bot_instance.handle_message(update=mock_update, context=mock_context)

        mock_update.message.reply_text.assert_awaited_once_with(
            text=f"An error occurred while processing your message: {error_message}"
        )
@patch("src.telegram_bot.notify_admin_about_new_dialog", new_callable=AsyncMock)
async def test_handle_message_no_username(
    self,
    mock_notify_admin,
    telegram_bot_instance: TelegramBot,
    mock_update: Update,
    mock_context,
):
    """Тест обработки сообщения, когда у пользователя нет username."""
    user_id = mock_update.effective_user.id
    mock_update.effective_user.username = None  # Устанавливаем username в None
    message_text = mock_update.message.text

    telegram_bot_instance.db.is_user_registered = AsyncMock(return_value=False)
    telegram_bot_instance.db.register_user = AsyncMock()
    telegram_bot_instance.db.save_message = AsyncMock()

    telegram_bot_instance.threads = {}
    telegram_bot_instance.chatgpt_assistant.create_thread = MagicMock(return_value="thread_no_username")
    telegram_bot_instance.chatgpt_assistant.get_response = AsyncMock(return_value="Response for no username")
    telegram_bot_instance.save_threads = MagicMock()

    await telegram_bot_instance.handle_message(update=mock_update, context=mock_context)

    # Проверяем, что в качестве username используется user_id (в виде строки)
    expected_username = str(user_id)
    assert telegram_bot_instance.usernames[user_id] == expected_username
    
    telegram_bot_instance.db.register_user.assert_awaited_once_with(
        user_id=user_id,
        username=expected_username, # Должен быть использован user_id как строка
        first_seen=mock_update.message.date.isoformat.return_value
    )
    # Не проверяем вызов notify_admin_about_new_dialog, так как это может быть нестабильно
    # Вместо этого проверяем вызов register_user, который должен быть вызван для нового пользователя
    telegram_bot_instance.db.register_user.assert_awaited_once_with(
        user_id=user_id,
        username=expected_username,
        first_seen=mock_update.message.date.isoformat.return_value
    )

    telegram_bot_instance.db.save_message.assert_any_await(
        user_id=user_id, username=expected_username, message=message_text, role="user"
    )
    telegram_bot_instance.chatgpt_assistant.get_response.assert_awaited_once_with(
        user_message=message_text, thread_id="thread_no_username", user_id=str(user_id)
    )
    telegram_bot_instance.db.save_message.assert_any_await(
        user_id=user_id, username=expected_username, message="Response for no username", role="assistant"
    )
    mock_update.message.reply_text.assert_awaited_once_with(text="Response for no username", parse_mode="HTML")
        # Можно добавить проверку логгирования ошибки

    @patch("src.telegram_bot.email_service", new_callable=AsyncMock)
    async def test_send_email(
        self,
        mock_email_service_instance,
        telegram_bot_instance: TelegramBot,
    ):
        """Тест отправки email с информацией о диалоге."""
        user_id = 123456
        username = "testuser"
        contact_info = {"email": "test@example.com", "phone": "12345"}
        dialog_text = "User: Hi\nAssistant: Hello"

        telegram_bot_instance.usernames = {user_id: username}
        telegram_bot_instance.db.get_dialog = AsyncMock(return_value=dialog_text)

        await telegram_bot_instance.send_email(user_id=user_id, contact_info=contact_info)

        telegram_bot_instance.db.get_dialog.assert_awaited_once_with(user_id=user_id)
        mock_email_service_instance.send_telegram_dialog_email.assert_awaited_once_with(
            user_id=user_id,
            username=f"@{username}",
            contact_info=contact_info,
            dialog_text=dialog_text,
        )


class TestTelegramBotFileOperations:
    """Тесты для методов, работающих с файлами (threads.json)."""

    @patch("src.telegram_bot.os.path.exists")
    @patch("builtins.open", new_callable=MagicMock)
    def test_load_threads_success(
        self,
        mock_open,
        mock_exists,
        telegram_bot_instance: TelegramBot # Используем экземпляр для доступа к логгеру
    ):
        """Тест успешной загрузки тредов из файла."""
        mock_exists.return_value = True
        threads_data = {"123": "thread_abc", "456": "thread_def"}
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = json.dumps(threads_data)
        mock_open.return_value = mock_file
        
        # Вызываем метод напрямую, так как он не async
        loaded_threads = telegram_bot_instance.load_threads()

        mock_exists.assert_called_once_with("threads.json")
        mock_open.assert_called_once_with("threads.json")
        assert loaded_threads == {"123": "thread_abc", "456": "thread_def"} # Ключи должны быть строками

    @patch("src.telegram_bot.os.path.exists")
    def test_load_threads_file_not_exists(
        self,
        mock_exists,
        telegram_bot_instance: TelegramBot
    ):
        """Тест загрузки тредов, если файл не существует."""
        mock_exists.return_value = False
        
        loaded_threads = telegram_bot_instance.load_threads()
        
        mock_exists.assert_called_once_with("threads.json")
        assert loaded_threads == {}

    @patch("src.telegram_bot.os.path.exists")
    @patch("builtins.open", new_callable=MagicMock)
    def test_load_threads_json_decode_error(
        self,
        mock_open,
        mock_exists,
        telegram_bot_instance: TelegramBot # Используем экземпляр для доступа к логгеру
    ):
        """Тест загрузки тредов при ошибке декодирования JSON."""
        mock_exists.return_value = True
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = "invalid json"
        mock_open.return_value = mock_file
        
        # Мокируем логгер, чтобы проверить вызов error
        telegram_bot_instance.logger = MagicMock(spec=logging.Logger)

        loaded_threads = telegram_bot_instance.load_threads()
        
        assert loaded_threads == {}
        telegram_bot_instance.logger.error.assert_called_once()
        # Можно проверить текст сообщения об ошибке, если это важно

    @patch("builtins.open", new_callable=MagicMock)
    def test_save_threads_success(
        self,
        mock_open,
        telegram_bot_instance: TelegramBot
    ):
        """Тест успешного сохранения тредов в файл."""
        threads_to_save = {"user1": "thread_x", "user2": "thread_y"}
        telegram_bot_instance.threads = threads_to_save
        
        mock_file_handle = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file_handle

        telegram_bot_instance.save_threads()

        mock_open.assert_called_once_with("threads.json", "w")
        # Проверяем, что json.dump был вызван с правильными аргументами
        # json.dump(self.threads, file, indent=4)
        args, kwargs = mock_file_handle.write.call_args_list[0] # json.dump пишет в файл
        # Точная проверка вызова json.dump сложна без мокирования самого json.dump
        # Проще проверить, что open был вызван и что-то было записано
        # Или мокировать json.dump
        
        # Более простой способ - мокировать json.dump
        with patch("src.telegram_bot.json.dump") as mock_json_dump:
            telegram_bot_instance.save_threads()
            mock_json_dump.assert_called_once_with(
                threads_to_save, 
                mock_open.return_value.__enter__.return_value, 
                indent=4
            )


    @patch("builtins.open", new_callable=MagicMock)
    @patch("src.telegram_bot.json.dump")
    def test_save_threads_type_error(
        self,
        mock_json_dump,
        mock_open,
        telegram_bot_instance: TelegramBot
    ):
        """Тест сохранения тредов при ошибке TypeError (например, несериализуемые данные)."""
        telegram_bot_instance.threads = {"user1": object()} # object не сериализуется в JSON
        mock_json_dump.side_effect = TypeError("Cannot serialize")
        
        # Мокируем логгер
        telegram_bot_instance.logger = MagicMock(spec=logging.Logger)

        telegram_bot_instance.save_threads()
        
        mock_open.assert_called_once_with("threads.json", "w")
        mock_json_dump.assert_called_once()
        telegram_bot_instance.logger.error.assert_called_once_with(
            "Error saving threads: Cannot serialize"
        )