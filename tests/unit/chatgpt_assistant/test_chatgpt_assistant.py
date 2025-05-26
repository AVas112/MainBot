"""Юнит-тесты для модуля ChatGPTAssistant."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import OpenAIError
from openai import models
from openai.types import beta
from openai.types.beta.threads import Run
from openai.types.beta.threads import (
    RequiredActionFunctionToolCall,
    RunSubmitToolOutputsParams
)

from src.chatgpt_assistant import ChatGPTAssistant


class TestChatGPTAssistantInit:
    """Тесты инициализации ChatGPTAssistant."""

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    def test_init_without_telegram_bot(self, mock_openai, mock_config, mock_proxy):
        """Тест инициализации без Telegram бота."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        # Act
        assistant = ChatGPTAssistant()

        # Assert
        assert assistant.api_key == "test-api-key"
        assert assistant.assistant_id == "test-assistant-id"
        assert assistant.telegram_bot is None
        assert assistant.client == mock_openai_instance
        mock_openai.assert_called_once_with(
            api_key="test-api-key",
            default_headers={"OpenAI-Beta": "assistants=v2"}
        )

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    def test_init_with_telegram_bot(self, mock_openai, mock_config, mock_proxy, mock_telegram_bot):
        """Тест инициализации с Telegram ботом."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        # Act
        assistant = ChatGPTAssistant(telegram_bot=mock_telegram_bot)

        # Assert
        assert assistant.telegram_bot == mock_telegram_bot

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    def test_init_with_proxy(self, mock_openai, mock_config, mock_proxy):
        """Тест инициализации с прокси."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy_client = MagicMock()
        mock_proxy.return_value = mock_proxy_client
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        # Act
        assistant = ChatGPTAssistant()

        # Assert
        mock_openai.assert_called_once_with(
            api_key="test-api-key",
            default_headers={"OpenAI-Beta": "assistants=v2"},
            http_client=mock_proxy_client
        )


class TestChatGPTAssistantCreateThread:
    """Тесты создания треда."""

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    def test_create_thread_success(self, mock_openai, mock_config, mock_proxy):
        """Тест успешного создания треда."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_thread = MagicMock()
        mock_thread.id = "thread-123"
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.create.return_value = mock_thread
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()

        # Act
        thread_id = assistant.create_thread(user_id="user-123")

        # Assert
        assert thread_id == "thread-123"
        mock_openai_instance.beta.threads.create.assert_called_once()


class TestChatGPTAssistantAddUserMessage:
    """Тесты добавления сообщения пользователя."""

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    def test_add_user_message_success(self, mock_openai, mock_config, mock_proxy):
        """Тест успешного добавления сообщения пользователя."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()

        # Act
        assistant.add_user_message(thread_id="thread-123", message="Hello, assistant!")

        # Assert
        mock_openai_instance.beta.threads.messages.create.assert_called_once_with(
            thread_id="thread-123",
            role="user",
            content="Hello, assistant!"
        )


class TestChatGPTAssistantCreateRun:
    """Тесты создания run."""

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    def test_create_run_success(self, mock_openai, mock_config, mock_proxy):
        """Тест успешного создания run."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_run = MagicMock(spec=Run)
        mock_run.id = "run-123"
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.runs.create.return_value = mock_run
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()

        # Act
        run = assistant.create_run(thread_id="thread-123")

        # Assert
        assert run == mock_run
        mock_openai_instance.beta.threads.runs.create.assert_called_once_with(
            thread_id="thread-123",
            assistant_id="test-assistant-id"
        )


class TestChatGPTAssistantGetResponse:
    """Тесты получения ответа от ассистента."""

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_get_response_success(self, mock_openai, mock_config, mock_proxy):
        """Тест успешного получения ответа."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_run = MagicMock(spec=Run)
        mock_run.id = "run-123"
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.runs.create.return_value = mock_run
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()
        
        # Мокаем методы
        assistant.add_user_message = MagicMock()
        assistant.create_run = MagicMock(return_value=mock_run)
        assistant.process_run = AsyncMock(return_value="Test response")

        # Act
        response = await assistant.get_response(
            user_message="Hello",
            thread_id="thread-123",
            user_id="user-123"
        )

        # Assert
        assert response == "Test response"
        assistant.add_user_message.assert_called_once_with(
            thread_id="thread-123",
            message="Hello"
        )
        assistant.create_run.assert_called_once_with(thread_id="thread-123")
        assistant.process_run.assert_called_once_with(
            run=mock_run,
            thread_id="thread-123",
            user_id="user-123",
            retry_count=0
        )

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_get_response_openai_error(self, mock_openai, mock_config, mock_proxy):
        """Тест обработки ошибки OpenAI."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()
        assistant.add_user_message = MagicMock(side_effect=OpenAIError("API Error"))

        # Act & Assert
        with pytest.raises(OpenAIError):
            await assistant.get_response(
                user_message="Hello",
                thread_id="thread-123",
                user_id="user-123"
            )

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_get_response_unexpected_error(self, mock_openai, mock_config, mock_proxy):
        """Тест обработки неожиданной ошибки."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()
        assistant.add_user_message = MagicMock(side_effect=ValueError("Unexpected error"))

        # Act & Assert
        with pytest.raises(ValueError):
            await assistant.get_response(
                user_message="Hello",
                thread_id="thread-123",
                user_id="user-123"
            )


class TestChatGPTAssistantGetAssistantResponse:
    """Тесты получения ответа ассистента."""

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_get_assistant_response_success(self, mock_openai, mock_config, mock_proxy):
        """Тест успешного получения ответа ассистента."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        # Создаем мок сообщения
        mock_text = MagicMock()
        mock_text.value = "**Bold text** and [link](http://example.com) 【citation】"
        
        mock_content = MagicMock()
        mock_content.text = mock_text
        
        mock_message = MagicMock()
        mock_message.role = "assistant"
        mock_message.content = [mock_content]
        
        mock_messages = MagicMock()
        mock_messages.data = [mock_message]
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.messages.list.return_value = mock_messages
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()

        # Act
        response = await assistant.get_assistant_response(thread_id="thread-123")

        # Assert
        expected_response = '<b>Bold text</b> and <a href="http://example.com">link</a> '
        assert response == expected_response
        mock_openai_instance.beta.threads.messages.list.assert_called_once_with(
            thread_id="thread-123"
        )

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_get_assistant_response_no_message(self, mock_openai, mock_config, mock_proxy):
        """Тест получения ответа когда нет сообщения от ассистента."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_messages = MagicMock()
        mock_messages.data = []
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.messages.list.return_value = mock_messages
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()

        # Act
        response = await assistant.get_assistant_response(thread_id="thread-123")

        # Assert
        assert response == "Sorry, failed to get a response. Please try again."

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_get_assistant_response_empty_content(self, mock_openai, mock_config, mock_proxy):
        """Тест получения ответа с пустым содержимым."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_message = MagicMock()
        mock_message.role = "assistant"
        mock_message.content = None
        
        mock_messages = MagicMock()
        mock_messages.data = [mock_message]
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.messages.list.return_value = mock_messages
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()

        # Act
        response = await assistant.get_assistant_response(thread_id="thread-123")

        # Assert
        assert response == "Sorry, failed to get a response. Please try again."


class TestChatGPTAssistantProcessRun:
    """Тесты обработки run."""

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_process_run_completed(self, mock_sleep, mock_openai, mock_config, mock_proxy):
        """Тест обработки завершенного run."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_run = MagicMock(spec=Run)
        mock_run.id = "run-123"
        mock_run.status = "completed"
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.runs.retrieve.return_value = mock_run
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()
        assistant.get_assistant_response = AsyncMock(return_value="Test response")

        # Act
        response = await assistant.process_run(
            run=mock_run,
            thread_id="thread-123",
            user_id="user-123",
            retry_count=0
        )

        # Assert
        assert response == "Test response"
        assistant.get_assistant_response.assert_called_once_with(thread_id="thread-123")

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_process_run_requires_action(self, mock_sleep, mock_openai, mock_config, mock_proxy):
        """Тест обработки run требующего действий."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        # Первый вызов - requires_action, второй - completed
        mock_run_action = MagicMock(spec=Run)
        mock_run_action.id = "run-123"
        mock_run_action.status = "requires_action"
        
        mock_run_completed = MagicMock(spec=Run)
        mock_run_completed.id = "run-123"
        mock_run_completed.status = "completed"
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.runs.retrieve.side_effect = [
            mock_run_action,
            mock_run_completed
        ]
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()
        assistant.handle_required_action = AsyncMock(return_value=mock_run_completed)
        assistant.get_assistant_response = AsyncMock(return_value="Test response")

        # Act
        response = await assistant.process_run(
            run=mock_run_action,
            thread_id="thread-123",
            user_id="user-123",
            retry_count=0
        )

        # Assert
        assert response == "Test response"
        assistant.handle_required_action.assert_called_once_with(
            run=mock_run_action,
            thread_id="thread-123",
            user_id="user-123"
        )

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_process_run_failed_with_retry(self, mock_sleep, mock_openai, mock_config, mock_proxy):
        """Тест обработки неудачного run с повтором."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_run_failed = MagicMock(spec=Run)
        mock_run_failed.id = "run-123"
        mock_run_failed.status = "failed"
        
        mock_run_new = MagicMock(spec=Run)
        mock_run_new.id = "run-456"
        mock_run_new.status = "completed"
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.runs.retrieve.side_effect = [
            mock_run_failed,
            mock_run_new
        ]
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()
        assistant.create_run = MagicMock(return_value=mock_run_new)
        assistant.get_assistant_response = AsyncMock(return_value="Test response")

        # Act
        response = await assistant.process_run(
            run=mock_run_failed,
            thread_id="thread-123",
            user_id="user-123",
            retry_count=0
        )

        # Assert
        assert response == "Test response"
        assistant.create_run.assert_called_once_with("thread-123")

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_process_run_max_retries_reached(self, mock_sleep, mock_openai, mock_config, mock_proxy):
        """Тест обработки run при достижении максимального количества повторов."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_run_failed = MagicMock(spec=Run)
        mock_run_failed.id = "run-123"
        mock_run_failed.status = "failed"
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.runs.retrieve.return_value = mock_run_failed
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()
        assistant.get_assistant_response = AsyncMock(return_value="Fallback response")

        # Act
        response = await assistant.process_run(
            run=mock_run_failed,
            thread_id="thread-123",
            user_id="user-123",
            retry_count=3  # Максимальное количество повторов
        )

        # Assert
        assert response == "Fallback response"
        assistant.get_assistant_response.assert_called_once_with(thread_id="thread-123")


class TestChatGPTAssistantHandleRequiredAction:
    """Тесты обработки требуемых действий."""

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_handle_required_action_contact_info(self, mock_openai, mock_config, mock_proxy):
        """Тест обработки действия получения контактной информации."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        # Создаем мок tool call
        mock_tool_call = MagicMock(spec=RequiredActionFunctionToolCall)
        mock_tool_call.id = "tool-call-123"
        mock_tool_call.function = MagicMock()
        mock_tool_call.function.name = "get_client_contact_info"
        mock_tool_call.function.arguments = '{"name": "John", "phone": "+1234567890"}'
        
        # Создаем мок required_action
        mock_run = MagicMock(spec=Run)
        mock_run.id = "run-123"
        mock_run.required_action = MagicMock()
        mock_run.required_action.type = "submit_tool_outputs"
        mock_run.required_action.submit_tool_outputs = MagicMock()
        mock_run.required_action.submit_tool_outputs.tool_calls = [mock_tool_call]
        
        mock_updated_run = MagicMock(spec=Run)
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.runs.submit_tool_outputs.return_value = mock_updated_run
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()
        assistant.process_contact_info_tool_call = AsyncMock(return_value={
            "tool_call_id": "tool-call-123",
            "output": '{"status": "success", "message": "Contact information saved"}'
        })

        # Act
        result = await assistant.handle_required_action(
            run=mock_run,
            thread_id="thread-123",
            user_id="user-123"
        )

        # Assert
        assert result == mock_updated_run
        assistant.process_contact_info_tool_call.assert_called_once_with(
            tool_call=mock_tool_call,
            user_id="user-123"
        )
        mock_openai_instance.beta.threads.runs.submit_tool_outputs.assert_called_once_with(
            thread_id="thread-123",
            run_id="run-123",
            tool_outputs=[{
                "tool_call_id": "tool-call-123",
                "output": '{"status": "success", "message": "Contact information saved"}'
            }]
        )


class TestChatGPTAssistantProcessContactInfo:
    """Тесты обработки контактной информации."""

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_process_contact_info_tool_call_success(self, mock_openai, mock_config, mock_proxy):
        """Тест успешной обработки контактной информации."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        mock_tool_call = MagicMock()
        mock_tool_call.id = "tool-call-123"
        mock_tool_call.function.arguments = '{"name": "John", "phone": "+1234567890"}'

        assistant = ChatGPTAssistant()
        assistant.send_contact_notification = AsyncMock()

        # Act
        result = await assistant.process_contact_info_tool_call(
            tool_call=mock_tool_call,
            user_id="user-123"
        )

        # Assert
        expected_result = {
            "tool_call_id": "tool-call-123",
            "output": json.dumps({
                "status": "success",
                "message": "Contact information saved and notification sent"
            })
        }
        assert result == expected_result
        assistant.send_contact_notification.assert_called_once_with(
            user_id="user-123",
            contact_info={"name": "John", "phone": "+1234567890"}
        )


class TestChatGPTAssistantSendContactNotification:
    """Тесты отправки уведомлений о контактах."""

    @patch("src.chatgpt_assistant.email_service")
    @patch("src.chatgpt_assistant.notify_admin_about_successful_dialog")
    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_send_contact_notification_success(
        self,
        mock_openai,
        mock_config,
        mock_proxy,
        mock_notify_admin,
        mock_email_service,
        mock_telegram_bot
    ):
        """Тест успешной отправки уведомления о контакте."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        mock_email_service.send_telegram_dialog_email = AsyncMock()
        mock_notify_admin.return_value = AsyncMock()

        assistant = ChatGPTAssistant(telegram_bot=mock_telegram_bot)
        contact_info = {"name": "John", "phone": "+1234567890"}

        # Act
        await assistant.send_contact_notification(
            user_id="123456",
            contact_info=contact_info
        )

        # Assert
        mock_email_service.send_telegram_dialog_email.assert_called_once_with(
            user_id=123456,
            username="test_user",
            contact_info=contact_info,
            dialog_text="Test dialog text",
            db=mock_telegram_bot.db
        )
        mock_notify_admin.assert_called_once_with(
            bot=mock_telegram_bot.bot,
            user_id=123456,
            username="test_user",
            contact_info=contact_info
        )

    @patch("src.chatgpt_assistant.email_service")
    @patch("src.chatgpt_assistant.notify_admin_about_successful_dialog")
    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_send_contact_notification_hidden_username(
        self,
        mock_openai,
        mock_config,
        mock_proxy,
        mock_notify_admin,
        mock_email_service,
        mock_telegram_bot
    ):
        """Тест отправки уведомления когда пользователь скрыл имя."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        mock_email_service.send_telegram_dialog_email = AsyncMock()
        mock_notify_admin.return_value = AsyncMock()

        # Пользователь не в списке usernames
        mock_telegram_bot.usernames = {}

        assistant = ChatGPTAssistant(telegram_bot=mock_telegram_bot)
        contact_info = {"name": "John", "phone": "+1234567890"}

        # Act
        await assistant.send_contact_notification(
            user_id="999999",
            contact_info=contact_info
        )

        # Assert
        mock_email_service.send_telegram_dialog_email.assert_called_once_with(
            user_id=999999,
            username="999999",  # Используется user_id как username
            contact_info=contact_info,
            dialog_text="Test dialog text",
            db=mock_telegram_bot.db
        )

    @patch("src.chatgpt_assistant.email_service")
    @patch("src.chatgpt_assistant.notify_admin_about_successful_dialog")
    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_send_contact_notification_error_handling(
        self,
        mock_openai,
        mock_config,
        mock_proxy,
        mock_notify_admin,
        mock_email_service,
        mock_telegram_bot
    ):
        """Тест обработки ошибок при отправке уведомления."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        mock_email_service.send_telegram_dialog_email = AsyncMock(
            side_effect=Exception("Email service error")
        )

        assistant = ChatGPTAssistant(telegram_bot=mock_telegram_bot)
        contact_info = {"name": "John", "phone": "+1234567890"}

        # Act - не должно вызывать исключение
        await assistant.send_contact_notification(
            user_id="123456",
            contact_info=contact_info
        )

        # Assert - проверяем, что ошибка была залогирована, но не вызвала исключение
        mock_email_service.send_telegram_dialog_email.assert_called_once()