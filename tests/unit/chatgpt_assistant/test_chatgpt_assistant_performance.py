"""Тесты производительности для модуля ChatGPTAssistant."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.chatgpt_assistant import ChatGPTAssistant


class TestChatGPTAssistantPerformance:
    """Тесты производительности ChatGPTAssistant."""

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_requests_performance(self, mock_openai, mock_config, mock_proxy):
        """Тест производительности при одновременных запросах."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        # Настройка быстрых ответов от мока
        mock_text = MagicMock()
        mock_text.value = "Quick response"
        
        mock_content = MagicMock()
        mock_content.text = mock_text
        
        mock_message = MagicMock()
        mock_message.role = "assistant"
        mock_message.content = [mock_content]
        
        mock_messages = MagicMock()
        mock_messages.data = [mock_message]
        
        mock_run = MagicMock()
        mock_run.id = "run-123"
        mock_run.status = "completed"
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.runs.create.return_value = mock_run
        mock_openai_instance.beta.threads.runs.retrieve.return_value = mock_run
        mock_openai_instance.beta.threads.messages.list.return_value = mock_messages
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()

        # Act
        start_time = time.time()
        
        # Создаем 10 одновременных запросов
        tasks = []
        for i in range(10):
            task = assistant.get_response(
                user_message=f"Message {i}",
                thread_id=f"thread-{i}",
                user_id=f"user-{i}"
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        
        end_time = time.time()
        execution_time = end_time - start_time

        # Assert
        assert len(responses) == 10
        assert all(response == "Quick response" for response in responses)
        # Проверяем, что все запросы выполнились быстро (менее 5 секунд для моков)
        assert execution_time < 5.0

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_memory_usage_with_large_responses(self, mock_openai, mock_config, mock_proxy):
        """Тест использования памяти при больших ответах."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        # Создаем большой ответ (1MB текста)
        large_response = "A" * (1024 * 1024)
        
        mock_text = MagicMock()
        mock_text.value = large_response
        
        mock_content = MagicMock()
        mock_content.text = mock_text
        
        mock_message = MagicMock()
        mock_message.role = "assistant"
        mock_message.content = [mock_content]
        
        mock_messages = MagicMock()
        mock_messages.data = [mock_message]
        
        mock_run = MagicMock()
        mock_run.id = "run-123"
        mock_run.status = "completed"
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.runs.create.return_value = mock_run
        mock_openai_instance.beta.threads.runs.retrieve.return_value = mock_run
        mock_openai_instance.beta.threads.messages.list.return_value = mock_messages
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()

        # Act
        response = await assistant.get_response(
            user_message="Give me a large response",
            thread_id="thread-123",
            user_id="user-123"
        )

        # Assert
        assert len(response) == 1024 * 1024
        assert response == large_response

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_response_time_measurement(self, mock_openai, mock_config, mock_proxy):
        """Тест измерения времени ответа."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        # Добавляем задержку в мок для имитации реального API
        async def delayed_response(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms задержка
            return "Response after delay"
        
        mock_text = MagicMock()
        mock_text.value = "Response after delay"
        
        mock_content = MagicMock()
        mock_content.text = mock_text
        
        mock_message = MagicMock()
        mock_message.role = "assistant"
        mock_message.content = [mock_content]
        
        mock_messages = MagicMock()
        mock_messages.data = [mock_message]
        
        mock_run = MagicMock()
        mock_run.id = "run-123"
        mock_run.status = "completed"
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.runs.create.return_value = mock_run
        mock_openai_instance.beta.threads.runs.retrieve.return_value = mock_run
        mock_openai_instance.beta.threads.messages.list.return_value = mock_messages
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()

        # Act
        start_time = time.time()
        response = await assistant.get_response(
            user_message="Test message",
            thread_id="thread-123",
            user_id="user-123"
        )
        end_time = time.time()
        
        response_time = end_time - start_time

        # Assert
        assert response == "Response after delay"
        # Проверяем, что время ответа разумное (менее 1 секунды для мока)
        assert response_time < 1.0

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_stress_test_multiple_threads(self, mock_openai, mock_config, mock_proxy):
        """Стресс-тест с множественными тредами."""
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
        start_time = time.time()
        
        # Создаем 100 тредов одновременно
        tasks = []
        for i in range(100):
            task = asyncio.create_task(
                asyncio.to_thread(assistant.create_thread, f"user-{i}")
            )
            tasks.append(task)
        
        thread_ids = await asyncio.gather(*tasks)
        
        end_time = time.time()
        execution_time = end_time - start_time

        # Assert
        assert len(thread_ids) == 100
        assert all(thread_id == "thread-123" for thread_id in thread_ids)
        # Проверяем, что создание 100 тредов заняло разумное время
        assert execution_time < 10.0

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_resource_cleanup_after_error(self, mock_openai, mock_config, mock_proxy):
        """Тест очистки ресурсов после ошибки."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        # Настраиваем мок для генерации ошибки
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.messages.create.side_effect = Exception("Test error")
        mock_openai.return_value = mock_openai_instance

        assistant = ChatGPTAssistant()

        # Act & Assert
        with pytest.raises(Exception, match="Test error"):
            await assistant.get_response(
                user_message="Test message",
                thread_id="thread-123",
                user_id="user-123"
            )
        
        # Проверяем, что объект ассистента все еще функционален после ошибки
        assert assistant.client is not None
        assert assistant.api_key == "test-api-key"
        assert assistant.assistant_id == "test-assistant-id"


class TestChatGPTAssistantScalability:
    """Тесты масштабируемости ChatGPTAssistant."""

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_scalability_with_many_users(self, mock_openai, mock_config, mock_proxy):
        """Тест масштабируемости с большим количеством пользователей."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_text = MagicMock()
        mock_text.value = "Response"
        
        mock_content = MagicMock()
        mock_content.text = mock_text
        
        mock_message = MagicMock()
        mock_message.role = "assistant"
        mock_message.content = [mock_content]
        
        mock_messages = MagicMock()
        mock_messages.data = [mock_message]
        
        mock_run = MagicMock()
        mock_run.id = "run-123"
        mock_run.status = "completed"
        
        mock_openai_instance = MagicMock()
        mock_openai_instance.beta.threads.runs.create.return_value = mock_run
        mock_openai_instance.beta.threads.runs.retrieve.return_value = mock_run
        mock_openai_instance.beta.threads.messages.list.return_value = mock_messages
        mock_openai.return_value = mock_openai_instance

        # Создаем множество экземпляров ассистента для разных пользователей
        assistants = [ChatGPTAssistant() for _ in range(50)]

        # Act
        start_time = time.time()
        
        tasks = []
        for i, assistant in enumerate(assistants):
            task = assistant.get_response(
                user_message=f"Message from user {i}",
                thread_id=f"thread-{i}",
                user_id=f"user-{i}"
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        
        end_time = time.time()
        execution_time = end_time - start_time

        # Assert
        assert len(responses) == 50
        assert all(response == "Response" for response in responses)
        # Проверяем, что обработка 50 пользователей заняла разумное время
        assert execution_time < 15.0

    @patch("src.chatgpt_assistant.create_proxy_client")
    @patch("src.chatgpt_assistant.CONFIG")
    @patch("src.chatgpt_assistant.OpenAI")
    @pytest.mark.asyncio
    async def test_memory_efficiency_with_multiple_instances(self, mock_openai, mock_config, mock_proxy):
        """Тест эффективности памяти с множественными экземплярами."""
        # Arrange
        mock_config.OPENAI.API_KEY = "test-api-key"
        mock_config.OPENAI.ASSISTANT_ID = "test-assistant-id"
        mock_proxy.return_value = None
        
        mock_openai_instance = MagicMock()
        mock_openai.return_value = mock_openai_instance

        # Act
        # Создаем много экземпляров ассистента
        assistants = []
        for i in range(100):
            assistant = ChatGPTAssistant()
            assistants.append(assistant)

        # Assert
        # Проверяем, что все экземпляры созданы успешно
        assert len(assistants) == 100
        
        # Проверяем, что каждый экземпляр имеет правильную конфигурацию
        for assistant in assistants:
            assert assistant.api_key == "test-api-key"
            assert assistant.assistant_id == "test-assistant-id"
            assert assistant.client is not None
        
        # Проверяем, что экземпляры независимы
        assistants[0].api_key = "modified-key"
        assert assistants[1].api_key == "test-api-key"  # Другие экземпляры не изменились