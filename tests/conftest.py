"""Конфигурация и фикстуры для тестов."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import OpenAI
from openai.types.beta.threads import Run
from openai.types.beta.threads.message import Message
from openai.types.beta.threads.text_content_block import TextContentBlock
from openai.types.beta.threads.text import Text


@pytest.fixture
def mock_config():
    """Мок конфигурации."""
    config_mock = MagicMock()
    config_mock.OPENAI.API_KEY = "test-api-key"
    config_mock.OPENAI.ASSISTANT_ID = "test-assistant-id"
    return config_mock


@pytest.fixture
def mock_openai_client():
    """Мок OpenAI клиента."""
    client_mock = MagicMock(spec=OpenAI)
    
    # Мок для создания треда
    thread_mock = MagicMock()
    thread_mock.id = "test-thread-id"
    client_mock.beta.threads.create.return_value = thread_mock
    
    # Мок для создания сообщения
    client_mock.beta.threads.messages.create.return_value = None
    
    # Мок для создания run
    run_mock = MagicMock(spec=Run)
    run_mock.id = "test-run-id"
    run_mock.status = "completed"
    client_mock.beta.threads.runs.create.return_value = run_mock
    client_mock.beta.threads.runs.retrieve.return_value = run_mock
    
    # Мок для получения сообщений
    text_mock = MagicMock(spec=Text)
    text_mock.value = "Test response from assistant"
    
    text_content_mock = MagicMock(spec=TextContentBlock)
    text_content_mock.text = text_mock
    
    message_mock = MagicMock(spec=Message)
    message_mock.role = "assistant"
    message_mock.content = [text_content_mock]
    
    messages_list_mock = MagicMock()
    messages_list_mock.data = [message_mock]
    client_mock.beta.threads.messages.list.return_value = messages_list_mock
    
    return client_mock


@pytest.fixture
def mock_telegram_bot():
    """Мок Telegram бота."""
    bot_mock = MagicMock()
    bot_mock.usernames = {123456: "test_user"}
    bot_mock.db = AsyncMock()
    bot_mock.db.get_dialog.return_value = "Test dialog text"
    bot_mock.bot = AsyncMock()
    return bot_mock


@pytest.fixture
def mock_email_service():
    """Мок email сервиса."""
    email_mock = AsyncMock()
    email_mock.send_telegram_dialog_email = AsyncMock()
    return email_mock


@pytest.fixture
def mock_notify_admin():
    """Мок функции уведомления администратора."""
    return AsyncMock()

