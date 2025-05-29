"""Интеграционные тесты для модуля ChatGPTAssistant."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import OpenAIError
from openai.types.beta.threads import Run
from openai.types.beta.threads import RequiredActionFunctionToolCall
from openai.types.beta.threads.run import RequiredAction, RequiredActionSubmitToolOutputs

from src.chatgpt_assistant import ChatGPTAssistant


class TestChatGPTAssistantIntegration:
    """Интеграционные тесты для полного цикла работы с ассистентом."""

    @patch("src.chatgpt_assistant.email_service")
    @patch("src.chatgpt_assistant.notify_admin_about_successful_dialog")
    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_full_conversation_flow_with_contact_collection(
        self,
        mock_sleep,
        mock_openai,
        mock_config,
        mock_proxy,
        mock_notify_admin,
        mock_email_service,
        mock_telegram_bot
    ):
        """Тест полного цикла разговора с получением контактной информации."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        # Настройка мока для создания треда
        mock_thread = MagicMock()
        mock_thread.id = "thread-123"
        
        # Настройка мока для tool call
        mock_function = MagicMock()
        mock_function.name = "get_client_contact_info"
        mock_function.arguments = '{"name": "John Doe", "phone": "+1234567890", "email": "john@example.com"}'
        
        mock_tool_call = MagicMock(spec=RequiredActionFunctionToolCall)
        mock_tool_call.id = "tool-call-123"
        mock_tool_call.type = "function"
        mock_tool_call.function = mock_function
        
        mock_submit_tool_outputs = MagicMock(spec=RequiredActionSubmitToolOutputs)
        mock_submit_tool_outputs.tool_calls = [mock_tool_call]
        
        mock_required_action = MagicMock(spec=RequiredAction)
        mock_required_action.submit_tool_outputs = mock_submit_tool_outputs
        
        # Настройка последовательности статусов run
        mock_run_requires_action = MagicMock(spec=Run)
        mock_run_requires_action.id = "run-123"
        mock_run_requires_action.status = "requires_action"
        mock_run_requires_action.required_action = mock_required_action
        
        mock_run_completed = MagicMock(spec=Run)
        mock_run_completed.id = "run-123"
        mock_run_completed.status = "completed"
        
        # Настройка мока ответа ассистента
        mock_text = MagicMock()
        mock_text.value = "Спасибо за предоставленную информацию! Мы свяжемся с вами в ближайшее время."
        
        mock_content = MagicMock()
        mock_content.text = mock_text
        
        mock_message = MagicMock()
        mock_message.role = "assistant"
        mock_message.content = [mock_content]
        
        mock_messages = MagicMock()
        mock_messages.data = [mock_message]
        
        # Настройка OpenAI клиента
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.create.return_value = mock_thread
        mock_openai_instance.beta.threads.runs.create.return_value = mock_run_requires_action
        mock_openai_instance.beta.threads.runs.retrieve.side_effect = [
            mock_run_requires_action,
            mock_run_completed
        ]
        mock_openai_instance.beta.threads.runs.submit_tool_outputs.return_value = mock_run_completed
        mock_openai_instance.beta.threads.messages.list.return_value = mock_messages
        mock_openai.return_value = mock_openai_instance
        
        # Настройка email сервиса
        mock_email_service.send_telegram_dialog_email = AsyncMock()
        mock_notify_admin.return_value = AsyncMock()

        # Act
        assistant = ChatGPTAssistant(telegram_bot=mock_telegram_bot)
        
        # Создание треда
        thread_id = assistant.create_thread(user_id="123456")
        
        # Получение ответа с обработкой контактной информации
        response = await assistant.get_response(
            user_message="Меня зовут John Doe, мой телефон +1234567890, email john@example.com",
            thread_id=thread_id,
            user_id="123456"
        )

        # Assert
        assert thread_id == "thread-123"
        assert response == "Спасибо за предоставленную информацию! Мы свяжемся с вами в ближайшее время."
        
        # Проверяем, что сообщение пользователя было добавлено
        mock_openai_instance.beta.threads.messages.create.assert_called_once_with(
            thread_id="thread-123",
            role="user",
            content="Меня зовут John Doe, мой телефон +1234567890, email john@example.com"
        )
        
        # Проверяем, что был создан run
        mock_openai_instance.beta.threads.runs.create.assert_called_once_with(
            thread_id="thread-123",
            assistant_id="test-assistant-id"
        )
        
        # Проверяем, что были обработаны tool outputs
        mock_openai_instance.beta.threads.runs.submit_tool_outputs.assert_called_once()
        
        # Проверяем, что было отправлено email уведомление
        mock_email_service.send_telegram_dialog_email.assert_called_once_with(
            user_id=123456,
            username="test_user",
            contact_info={"name": "John Doe", "phone": "+1234567890", "email": "john@example.com"},
            dialog_text="Test dialog text",
            db=mock_telegram_bot.db
        )

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_conversation_with_multiple_retries(
        self,
        mock_sleep,
        mock_openai,
        mock_config,
        mock_proxy
    ):
        """Тест разговора с несколькими повторными попытками."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        # Настройка последовательности неудачных и успешного run
        mock_run_failed_1 = MagicMock(spec=Run)
        mock_run_failed_1.id = "run-123"
        mock_run_failed_1.status = "failed"
        
        mock_run_failed_2 = MagicMock(spec=Run)
        mock_run_failed_2.id = "run-456"
        mock_run_failed_2.status = "expired"
        
        mock_run_success = MagicMock(spec=Run)
        mock_run_success.id = "run-789"
        mock_run_success.status = "completed"
        
        # Настройка ответа ассистента
        mock_text = MagicMock()
        mock_text.value = "Извините за задержку. Как дела?"
        
        mock_content = MagicMock()
        mock_content.text = mock_text
        
        mock_message = MagicMock()
        mock_message.role = "assistant"
        mock_message.content = [mock_content]
        
        mock_messages = MagicMock()
        mock_messages.data = [mock_message]
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.runs.create.side_effect = [
            mock_run_failed_1,
            mock_run_failed_2,
            mock_run_success
        ]
        mock_openai_instance.beta.threads.runs.retrieve.side_effect = [
            mock_run_failed_1,
            mock_run_failed_2,
            mock_run_success
        ]
        mock_openai_instance.beta.threads.messages.list.return_value = mock_messages
        mock_openai.return_value = mock_openai_instance

        # Act
        assistant = ChatGPTAssistant()
        response = await assistant.get_response(
            user_message="Привет!",
            thread_id="thread-123",
            user_id="user-123"
        )

        # Assert
        assert response == "Извините за задержку. Как дела?"
        # Проверяем, что было создано 3 run (первый + 2 повтора)
        assert mock_openai_instance.beta.threads.runs.create.call_count == 3

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_conversation_with_network_error(
        self,
        mock_openai,
        mock_config,
        mock_proxy
    ):
        """Тест обработки сетевых ошибок."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.messages.create.side_effect = OpenAIError("Network error")
        mock_openai.return_value = mock_openai_instance

        # Act & Assert
        assistant = ChatGPTAssistant()
        with pytest.raises(OpenAIError, match="Network error"):
            await assistant.get_response(
                user_message="Привет!",
                thread_id="thread-123",
                user_id="user-123"
            )

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_conversation_with_long_running_process(
        self,
        mock_sleep,
        mock_openai,
        mock_config,
        mock_proxy
    ):
        """Тест разговора с длительным процессом обработки."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        # Настройка последовательности статусов: in_progress -> queued -> completed
        mock_run_in_progress = MagicMock(spec=Run)
        mock_run_in_progress.id = "run-123"
        mock_run_in_progress.status = "in_progress"
        
        mock_run_queued = MagicMock(spec=Run)
        mock_run_queued.id = "run-123"
        mock_run_queued.status = "queued"
        
        mock_run_completed = MagicMock(spec=Run)
        mock_run_completed.id = "run-123"
        mock_run_completed.status = "completed"
        
        mock_text = MagicMock()
        mock_text.value = "Обработка завершена успешно!"
        
        mock_content = MagicMock()
        mock_content.text = mock_text
        
        mock_message = MagicMock()
        mock_message.role = "assistant"
        mock_message.content = [mock_content]
        
        mock_messages = MagicMock()
        mock_messages.data = [mock_message]
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.runs.create.return_value = mock_run_in_progress
        mock_openai_instance.beta.threads.runs.retrieve.side_effect = [
            mock_run_in_progress,
            mock_run_queued,
            mock_run_completed
        ]
        mock_openai_instance.beta.threads.messages.list.return_value = mock_messages
        mock_openai.return_value = mock_openai_instance

        # Act
        assistant = ChatGPTAssistant()
        response = await assistant.get_response(
            user_message="Выполни сложную задачу",
            thread_id="thread-123",
            user_id="user-123"
        )

        # Assert
        assert response == "Обработка завершена успешно!"
        assert mock_openai_instance.beta.threads.runs.retrieve.call_count == 3
        assert mock_sleep.call_count == 2


class TestChatGPTAssistantEdgeCases:
    """Тесты граничных случаев и обработки ошибок."""

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_malformed_json_in_tool_call(self, mock_openai, mock_config, mock_proxy):
        """Тест обработки некорректного JSON в tool call."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        mock_tool_call = MagicMock()
        mock_tool_call.id = "tool-call-123"
        mock_tool_call.function.arguments = '{"name": "John", "phone": "+123'

        assistant = ChatGPTAssistant()

        # Act & Assert
        with pytest.raises(json.JSONDecodeError):
            await assistant.process_contact_info_tool_call(
                tool_call=mock_tool_call,
                user_id="user-123"
            )

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_empty_message_content(self, mock_openai, mock_config, mock_proxy):
        """Тест обработки пустого содержимого сообщения."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_message = MagicMock()
        mock_message.role = "assistant"
        mock_message.content = []
        
        mock_messages = MagicMock()
        mock_messages.data = [mock_message]
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.messages.list.return_value = mock_messages
        mock_openai.return_value = mock_openai_instance

        # Act
        assistant = ChatGPTAssistant()
        response = await assistant.get_assistant_response(thread_id="thread-123")

        # Assert
        assert response == "Sorry, failed to get a response. Please try again."

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_unicode_characters_in_response(self, mock_openai, mock_config, mock_proxy):
        """Тест обработки Unicode символов в ответе."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_text = MagicMock()
        mock_text.value = "Привет! 🤖 Как дела? **Жирный текст** и [ссылка](https://example.com) 【цитата】"
        
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

        # Act
        assistant = ChatGPTAssistant()
        response = await assistant.get_assistant_response(thread_id="thread-123")

        # Assert
        expected_response = 'Привет! 🤖 Как дела? <b>Жирный текст</b> и <a href="https://example.com">ссылка</a> '
        assert response == expected_response

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_very_long_message(self, mock_openai, mock_config, mock_proxy):
        """Тест обработки очень длинного сообщения."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        long_message = "A" * 10000
        
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        # Act
        assistant = ChatGPTAssistant()
        assistant.add_user_message(thread_id="thread-123", message=long_message)

        # Assert
        mock_openai_instance.beta.threads.messages.create.assert_called_once_with(
            thread_id="thread-123",
            role="user",
            content=long_message
        )

    @patch("src.chatgpt_assistant.email_service")
    @patch("src.chatgpt_assistant.notify_admin_about_successful_dialog")
    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_telegram_bot_without_db_attribute(
        self,
        mock_openai,
        mock_config,
        mock_proxy,
        mock_notify_admin,
        mock_email_service
    ):
        """Тест работы с Telegram ботом без атрибута db."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        mock_email_service.send_telegram_dialog_email = AsyncMock()
        mock_notify_admin.return_value = AsyncMock()

        mock_telegram_bot = MagicMock()
        mock_telegram_bot.usernames = {123456: "test_user"}
        mock_telegram_bot.bot = AsyncMock()
        
        mock_get_dialog = AsyncMock()
        mock_get_dialog.return_value = "Test dialog text"
        
        mock_db = MagicMock()
        mock_db.get_dialog = mock_get_dialog
        
        mock_telegram_bot.db = mock_db

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
            db=mock_db
        )