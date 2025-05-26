import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

# Загрузка конфигурации перед импортом других модулей, которые могут ее использовать
from dotenv import load_dotenv
load_dotenv(override=True)

# Устанавливаем переменные для ReminderConfig, если они не заданы,
# т.к. CONFIG их ожидает при инициализации OpenAIConfig -> CONFIG -> ReminderConfig
import os
os.environ.setdefault("REMINDER_ENABLED", "True")
os.environ.setdefault("REMINDER_FIRST_REMINDER_TIME", "60")
os.environ.setdefault("REMINDER_SECOND_REMINDER_TIME", "120")
os.environ.setdefault("REMINDER_FIRST_REMINDER_PROMPT", "Test first prompt {minutes}")
os.environ.setdefault("REMINDER_SECOND_REMINDER_PROMPT", "Test second prompt {minutes}")

from src.chatgpt_assistant import ChatGPTAssistant
from src.config.config import CONFIG # CONFIG уже должен быть инициализирован с .env


# Фикстуры для моков зависимостей
@pytest.fixture
def mock_telegram_bot():
    bot = MagicMock()
    bot.usernames = {123: "testuser"}
    bot.db = AsyncMock() # Мокаем db, так как send_contact_notification его использует
    bot.db.get_dialog = AsyncMock(return_value=["User: Hello", "Assistant: Hi"])
    bot.bot = AsyncMock() # Для notify_admin_about_successful_dialog
    return bot

@pytest.fixture
def mock_openai_client():
    client = MagicMock()
    client.beta = MagicMock()
    client.beta.threads = MagicMock()
    client.beta.threads.create = MagicMock(return_value=MagicMock(id="test_thread_id"))
    client.beta.threads.messages = MagicMock()
    client.beta.threads.messages.create = AsyncMock() # add_user_message теперь асинхронный в OpenAI v1.x+
    client.beta.threads.runs = MagicMock()
    client.beta.threads.runs.create = MagicMock(return_value=MagicMock(id="test_run_id", status="queued"))
    client.beta.threads.runs.retrieve = MagicMock() # Будет настраиваться в тестах
    client.beta.threads.runs.submit_tool_outputs = MagicMock(return_value=MagicMock(id="test_run_id", status="queued"))
    return client

@pytest.fixture
@patch('src.utils.proxy.create_proxy_client', return_value=None) # Мокаем прокси клиент
def assistant(create_proxy_client, mock_telegram_bot, mock_openai_client): # Parameter order changed
    # Мокаем OpenAI клиент прямо при создании ассистента
    with patch('openai.OpenAI', return_value=mock_openai_client):
        # Убедимся, что CONFIG корректно загружен и OpenAIConfig имеет нужные значения
        assert CONFIG.OPENAI.API_KEY is not None
        assert CONFIG.OPENAI.ASSISTANT_ID is not None
        assistant_instance = ChatGPTAssistant(telegram_bot=mock_telegram_bot)
        assistant_instance.client = mock_openai_client # Присваиваем мок клиента
        return assistant_instance

# Тесты
@pytest.mark.asyncio
async def test_create_thread(assistant: ChatGPTAssistant, mock_openai_client):
    user_id = "user123"
    thread_id = assistant.create_thread(user_id=user_id)
    
    mock_openai_client.beta.threads.create.assert_called_once()
    assert thread_id == "test_thread_id"

@pytest.mark.asyncio
async def test_add_user_message(assistant: ChatGPTAssistant, mock_openai_client):
    thread_id = "test_thread_id"
    message = "Hello Assistant"
    
    # В OpenAI SDK v1.x и выше, messages.create является асинхронным
    # Если ваш ChatGPTAssistant.add_user_message синхронный, но вызывает асинхронный SDK метод,
    # то сам add_user_message должен быть async или использовать asyncio.run/create_task.
    # Судя по вашему коду, add_user_message - синхронный, но вызывает синхронный SDK метод.
    # Проверим, что это так в вашем коде. Если openai.OpenAI(...).beta.threads.messages.create - синхронная, то ок.
    # Однако, в последних версиях SDK многие вызовы стали async.
    # Предположим, что в вашем коде add_user_message вызывает синхронный client.beta.threads.messages.create
    # Если это не так, тест нужно будет адаптировать.
    # В моем моке mock_openai_client.beta.threads.messages.create = AsyncMock() - это неправильно для синхронного вызова
    # Исправляем мок для messages.create на MagicMock, если add_user_message синхронный
    mock_openai_client.beta.threads.messages.create = MagicMock()

    assistant.add_user_message(thread_id=thread_id, message=message)
    
    mock_openai_client.beta.threads.messages.create.assert_called_once_with(
        thread_id=thread_id,
        role="user",
        content=message
    )

@pytest.mark.asyncio
async def test_create_run(assistant: ChatGPTAssistant, mock_openai_client):
    thread_id = "test_thread_id"
    run = assistant.create_run(thread_id=thread_id)
    
    mock_openai_client.beta.threads.runs.create.assert_called_once_with(
        thread_id=thread_id,
        assistant_id=CONFIG.OPENAI.ASSISTANT_ID
    )
    assert run.id == "test_run_id"

@pytest.mark.asyncio
async def test_get_response_completed(assistant: ChatGPTAssistant, mock_openai_client):
    user_message = "What's the weather?"
    thread_id = "test_thread_id"
    user_id = "user123"
    expected_response = "The weather is sunny. **Bold text** [link](http://example.com)"
    formatted_response = "The weather is sunny. <b>Bold text</b> <a href=\"http://example.com\">link</a>"

    # Мок для add_user_message (синхронный вызов)
    mock_openai_client.beta.threads.messages.create = MagicMock()
    
    # Мок для create_run (синхронный вызов)
    mock_openai_client.beta.threads.runs.create = MagicMock(return_value=MagicMock(id="run1", status="queued"))

    # Мок для retrieve (синхронный вызов)
    mock_openai_client.beta.threads.runs.retrieve.return_value = MagicMock(
        id="run1",
        status="completed" # Сразу возвращаем completed
    )
    
    # Мок для list messages (синхронный вызов)
    mock_assistant_message = MagicMock()
    mock_assistant_message.role = "assistant"
    mock_assistant_message.content = [MagicMock(text=MagicMock(value=expected_response))]
    
    mock_user_message_obj = MagicMock() # Мок для сообщения пользователя в списке
    mock_user_message_obj.role = "user"

    mock_openai_client.beta.threads.messages.list.return_value = MagicMock(
        data=[mock_assistant_message, mock_user_message_obj] # Ответ ассистента первый в списке
    )

    response = await assistant.get_response(user_message, thread_id, user_id)
    
    assistant.client.beta.threads.messages.create.assert_called_once_with(thread_id=thread_id, role="user", content=user_message)
    assistant.client.beta.threads.runs.create.assert_called_once_with(thread_id=thread_id, assistant_id=assistant.assistant_id)
    assistant.client.beta.threads.runs.retrieve.assert_called_with(thread_id=thread_id, run_id="run1")
    assistant.client.beta.threads.messages.list.assert_called_with(thread_id=thread_id)
    assert response == formatted_response

@pytest.mark.asyncio
@patch('src.chatgpt_assistant.email_service.send_telegram_dialog_email', new_callable=AsyncMock)
@patch('src.chatgpt_assistant.notify_admin_about_successful_dialog', new_callable=AsyncMock)
async def test_get_response_requires_action(
    mock_notify_admin, mock_send_email, assistant: ChatGPTAssistant, mock_openai_client, mock_telegram_bot
):
    user_message = "Book a meeting"
    thread_id = "test_thread_id"
    user_id_str = "123" # user_id в assistant строковый
    
    contact_info_payload = {"name": "John Doe", "phone_number": "1234567890"}
    tool_call_id = "tool_call_1"

    # Этапы вызовов retrieve
    # 1. Первый retrieve возвращает requires_action
    # 2. После submit_tool_outputs, следующий retrieve (в цикле process_run) возвращает completed
    mock_openai_client.beta.threads.runs.retrieve.side_effect = [
        MagicMock(
            id="run_action", status="requires_action",
            required_action=MagicMock(
                submit_tool_outputs=MagicMock(
                    tool_calls=[
                        MagicMock(
                            id=tool_call_id,
                            function=MagicMock(
                                name="get_client_contact_info",
                                arguments=json.dumps(contact_info_payload)
                            )
                        )
                    ]
                )
            )
        ),
        MagicMock(id="run_action", status="completed") # После submit_tool_outputs
    ]

    # Мок для add_user_message
    mock_openai_client.beta.threads.messages.create = MagicMock()
    # Мок для create_run
    mock_openai_client.beta.threads.runs.create = MagicMock(return_value=MagicMock(id="run_action", status="queued"))
    # Мок для submit_tool_outputs
    mock_openai_client.beta.threads.runs.submit_tool_outputs = MagicMock(return_value=MagicMock(id="run_action", status="processing"))

    # Мок для list messages (после completed)
    final_response_text = "Action handled, meeting booked."
    mock_assistant_message = MagicMock(role="assistant", content=[MagicMock(text=MagicMock(value=final_response_text))])
    mock_openai_client.beta.threads.messages.list.return_value = MagicMock(data=[mock_assistant_message])

    # Мокаем db.get_dialog, который вызывается в send_contact_notification -> email_service.send_telegram_dialog_email
    mock_telegram_bot.db.get_dialog.return_value = ["User: Test dialog", "Assistant: Test response"]


    response = await assistant.get_response(user_message, thread_id, user_id_str)

    # Проверяем вызовы
    mock_openai_client.beta.threads.messages.create.assert_called_once()
    mock_openai_client.beta.threads.runs.create.assert_called_once()
    
    # Проверяем submit_tool_outputs
    mock_openai_client.beta.threads.runs.submit_tool_outputs.assert_called_once()
    call_args = mock_openai_client.beta.threads.runs.submit_tool_outputs.call_args
    assert call_args[1]['thread_id'] == thread_id
    assert call_args[1]['run_id'] == "run_action"
    assert len(call_args[1]['tool_outputs']) == 1
    assert call_args[1]['tool_outputs'][0]['tool_call_id'] == tool_call_id
    output_dict = json.loads(call_args[1]['tool_outputs'][0]['output'])
    assert output_dict['status'] == "success"

    # Проверяем, что уведомления были отправлены
    mock_send_email.assert_called_once()
    # Аргументы send_telegram_dialog_email: user_id, username, contact_info, dialog_text, db
    email_args = mock_send_email.call_args[0]
    assert email_args[0] == int(user_id_str) # user_id
    assert email_args[1] == mock_telegram_bot.usernames[int(user_id_str)] # username
    assert email_args[2] == contact_info_payload # contact_info

    mock_notify_admin.assert_called_once()
    admin_notify_args = mock_notify_admin.call_args[0]
    assert admin_notify_args[1] == int(user_id_str) # user_id
    assert admin_notify_args[2] == mock_telegram_bot.usernames[int(user_id_str)] # username
    assert admin_notify_args[3] == contact_info_payload # contact_info
    
    assert response == final_response_text
    assert mock_openai_client.beta.threads.runs.retrieve.call_count == 2 # Первый раз requires_action, второй раз completed

@pytest.mark.asyncio
async def test_get_response_failed_run_with_retry_and_final_success(assistant: ChatGPTAssistant, mock_openai_client):
    user_message = "Test message"
    thread_id = "test_thread_id"
    user_id = "user789"
    final_expected_response = "Finally worked!"

    # Мок для add_user_message
    mock_openai_client.beta.threads.messages.create = MagicMock()

    # Первый create_run (используемый в get_response)
    mock_openai_client.beta.threads.runs.create.return_value = MagicMock(id="run_fail_1", status="queued")
    
    # Последующие create_run (используемые в process_run для повторных попыток)
    # Нам нужно, чтобы create_run возвращал разные объекты Run для каждой попытки
    # или чтобы retrieve менял статус одного и того же объекта Run
    
    # Попытка 1: failed
    # Попытка 2: failed
    # Попытка 3: completed
    
    # Настроим retrieve:
    # 1-й вызов retrieve для run_fail_1 -> failed
    #   process_run видит failed, создает новый run (run_fail_2)
    # 2-й вызов retrieve для run_fail_2 -> failed
    #   process_run видит failed, создает новый run (run_ok_3)
    # 3-й вызов retrieve для run_ok_3 -> completed
    
    mock_run_fail_1 = MagicMock(id="run_fail_1", status="failed")
    mock_run_fail_2 = MagicMock(id="run_fail_2", status="failed")
    mock_run_ok_3 = MagicMock(id="run_ok_3", status="completed")

    # Это будет немного сложнее настроить с одним mock_openai_client.beta.threads.runs.create
    # Давайте сделаем так: create будет возвращать разные ID при каждом вызове, а retrieve будет настроен на эти ID
    
    mock_openai_client.beta.threads.runs.create.side_effect = [
        MagicMock(id="run_initial", status="queued"), # Первый вызов из get_response
        MagicMock(id="run_retry_1", status="queued"), # Первый повторный вызов из process_run
        MagicMock(id="run_retry_2", status="queued")  # Второй повторный вызов из process_run
    ]

    def retrieve_side_effect(thread_id, run_id):
        if run_id == "run_initial":
            return MagicMock(id="run_initial", status="failed")
        elif run_id == "run_retry_1":
            return MagicMock(id="run_retry_1", status="failed")
        elif run_id == "run_retry_2":
            return MagicMock(id="run_retry_2", status="completed")
        return MagicMock(status="unknown") # На всякий случай

    mock_openai_client.beta.threads.runs.retrieve.side_effect = retrieve_side_effect

    # Мок для list messages (для успешного ответа в конце)
    mock_assistant_message = MagicMock(role="assistant", content=[MagicMock(text=MagicMock(value=final_expected_response))])
    mock_openai_client.beta.threads.messages.list.return_value = MagicMock(data=[mock_assistant_message])

    response = await assistant.get_response(user_message, thread_id, user_id)

    assert mock_openai_client.beta.threads.runs.create.call_count == 3 # initial + 2 retries
    # retrieve будет вызван для каждого run до его завершения или таймаута (здесь мы сразу даем failed/completed)
    # run_initial -> retrieve (failed)
    # run_retry_1 -> retrieve (failed)
    # run_retry_2 -> retrieve (completed)
    assert mock_openai_client.beta.threads.runs.retrieve.call_count == 3
    
    assert response == final_expected_response
    mock_openai_client.beta.threads.messages.list.assert_called_once_with(thread_id=thread_id)

@pytest.mark.asyncio
async def test_get_response_max_retries_reached(assistant: ChatGPTAssistant, mock_openai_client):
    user_message = "Persistent fail"
    thread_id = "test_thread_id"
    user_id = "user_max_retry"
    # Ожидаем дефолтный ответ, так как все попытки провалятся
    # Однако, ваш код вызывает get_assistant_response даже после max_retries,
    # так что он попытается получить последнее сообщение.
    # Если сообщений нет, он вернет "Sorry, failed to get a response..."
    
    # Мок для add_user_message
    mock_openai_client.beta.threads.messages.create = MagicMock()

    # Все попытки create_run и retrieve будут возвращать failed
    mock_openai_client.beta.threads.runs.create.return_value = MagicMock(id="run_always_fail", status="queued")
    mock_openai_client.beta.threads.runs.retrieve.return_value = MagicMock(id="run_always_fail", status="failed")

    # Мок для list messages, который будет вызван в конце, предположим, он не найдет сообщения ассистента
    mock_openai_client.beta.threads.messages.list.return_value = MagicMock(data=[])

    response = await assistant.get_response(user_message, thread_id, user_id)

    # MAX_RETRIES в коде ChatGPTAssistant = 3. Значит, будет 1 оригинальная попытка + 3 повторных = 4 вызова create_run
    # Но логика retry_count < max_retries (0 < 3, 1 < 3, 2 < 3) означает, что будет 1 + 3 = 4 попытки.
    # create_run будет вызван 1 (изначальный) + 3 (повторы) = 4 раза.
    # В вашей реализации:
    # 1. get_response -> create_run (1) -> process_run(run, retry_count=0)
    # 2. process_run -> retrieve (failed) -> retry_count=0 < 3 -> create_run (2) -> process_run(new_run, retry_count=1)
    # 3. process_run -> retrieve (failed) -> retry_count=1 < 3 -> create_run (3) -> process_run(new_run, retry_count=2)
    # 4. process_run -> retrieve (failed) -> retry_count=2 < 3 -> create_run (4) -> process_run(new_run, retry_count=3)
    # 5. process_run -> retrieve (failed) -> retry_count=3 not < 3 -> лог "Max retries reached" -> get_assistant_response
    assert mock_openai_client.beta.threads.runs.create.call_count == 4
    assert mock_openai_client.beta.threads.runs.retrieve.call_count == 4 # Каждый run проверяется один раз и сразу failed

    assert response == "Sorry, failed to get a response. Please try again."
    mock_openai_client.beta.threads.messages.list.assert_called_once_with(thread_id=thread_id)

# Очистка переменных окружения, установленных для тестов
def teardown_module(module):
    if "REMINDER_ENABLED" in os.environ: del os.environ["REMINDER_ENABLED"]
    if "REMINDER_FIRST_REMINDER_TIME" in os.environ: del os.environ["REMINDER_FIRST_REMINDER_TIME"]
    if "REMINDER_SECOND_REMINDER_TIME" in os.environ: del os.environ["REMINDER_SECOND_REMINDER_TIME"]
    if "REMINDER_FIRST_REMINDER_PROMPT" in os.environ: del os.environ["REMINDER_FIRST_REMINDER_PROMPT"]
    if "REMINDER_SECOND_REMINDER_PROMPT" in os.environ: del os.environ["REMINDER_SECOND_REMINDER_PROMPT"]
