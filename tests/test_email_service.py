import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, call
from string import Template
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Загрузка конфигурации перед импортом других модулей
from dotenv import load_dotenv
load_dotenv(override=True)

# Установка переменных для других конфигов, если они влияют на инициализацию CONFIG
import os
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake_token")
os.environ.setdefault("OPENAI_API_KEY", "fake_key")
os.environ.setdefault("OPENAI_ASSISTANT_ID", "fake_id")
# ... и так далее для всех ожидаемых CONFIG при импорте EmailService -> CONFIG
os.environ.setdefault("REMINDER_ENABLED", "True")
os.environ.setdefault("REMINDER_FIRST_REMINDER_TIME", "60")
os.environ.setdefault("REMINDER_SECOND_REMINDER_TIME", "120")
os.environ.setdefault("REMINDER_FIRST_REMINDER_PROMPT", "Test first prompt {minutes}")
os.environ.setdefault("REMINDER_SECOND_REMINDER_PROMPT", "Test second prompt {minutes}")


from src.utils.email_service import EmailService, email_service
from src.config.config import CONFIG # CONFIG должен быть уже правильно загружен

# Убедимся, что SMTP конфигурация загружена
assert CONFIG.SMTP.SERVER is not None
assert CONFIG.SMTP.PORT is not None
assert CONFIG.SMTP.USERNAME is not None
assert CONFIG.SMTP.PASSWORD is not None
assert CONFIG.SMTP.NOTIFICATION_EMAIL is not None


@pytest.fixture
def service():
    # Используем глобальный инстанс email_service, который уже инициализирован с CONFIG
    # или создаем новый, если хотим тестировать инициализацию
    return EmailService() # Создаем новый экземпляр для каждого теста для изоляции

@pytest.fixture
def mock_smtp_server():
    with patch('smtplib.SMTP') as mock_smtp:
        server_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server_instance
        yield server_instance


@pytest.mark.asyncio
async def test_send_email_custom_content(service: EmailService, mock_smtp_server):
    subject = "Test Subject"
    body_html = "<h1>Hello</h1><p>This is a test.</p>"
    recipient = "test@example.com"

    await service.send_email(subject=subject, body=body_html, recipient=recipient)

    mock_smtp_server.starttls.assert_called_once()
    mock_smtp_server.login.assert_called_once_with(CONFIG.SMTP.USERNAME, CONFIG.SMTP.PASSWORD)
    
    # Проверяем, что send_message был вызван
    assert mock_smtp_server.send_message.call_count == 1
    sent_msg: MIMEMultipart = mock_smtp_server.send_message.call_args[0][0]
    
    assert sent_msg["Subject"] == subject
    assert sent_msg["From"] == CONFIG.SMTP.USERNAME
    assert sent_msg["To"] == recipient
    
    # Проверяем наличие HTML и текстовой части
    assert sent_msg.is_multipart()
    payload = sent_msg.get_payload()
    assert len(payload) == 2 # Должно быть две части: text/plain и text/html
    
    html_part_found = False
    text_part_found = False
    for part in payload:
        if part.get_content_type() == "text/html":
            assert part.get_payload(decode=True).decode() == body_html
            html_part_found = True
        elif part.get_content_type() == "text/plain":
            # Проверяем, что текстовая часть содержит текст из HTML
            assert "Hello" in part.get_payload(decode=True).decode()
            assert "This is a test." in part.get_payload(decode=True).decode()
            text_part_found = True
            
    assert html_part_found and text_part_found

@pytest.mark.asyncio
async def test_send_email_with_contact_info(service: EmailService, mock_smtp_server):
    user_id = 123
    contact_info = {"name": "Test User", "email": "user@example.com"}
    
    await service.send_email(user_id=user_id, contact_info=contact_info)

    mock_smtp_server.login.assert_called_once_with(CONFIG.SMTP.USERNAME, CONFIG.SMTP.PASSWORD)
    sent_msg: MIMEMultipart = mock_smtp_server.send_message.call_args[0][0]
    
    assert sent_msg["Subject"] == f"Новая заявка от пользователя {user_id}"
    assert sent_msg["To"] == CONFIG.SMTP.NOTIFICATION_EMAIL # Получатель по умолчанию
    
    body_plain = ""
    for part in sent_msg.get_payload():
        if part.get_content_type() == "text/plain":
            body_plain = part.get_payload(decode=True).decode()
            break
    
    assert f"Получена новая заявка от пользователя {user_id}:" in body_plain
    assert "name: Test User" in body_plain
    assert "email: user@example.com" in body_plain


@pytest.mark.asyncio
async def test_send_email_insufficient_data(service: EmailService, mock_smtp_server):
    # Не передаем ни user_id/contact_info, ни subject/body
    await service.send_email()
    mock_smtp_server.send_message.assert_not_called() # Не должно быть попытки отправки

@pytest.mark.asyncio
async def test_send_telegram_dialog_email(service: EmailService, mock_smtp_server):
    user_id = 456
    username = "test_telegram_user"
    contact_info = {"name": "Tele User", "phone_number": "987654321"}
    dialog_text = ["User: Hello there", "ChatGPT: Hi! How can I help?"]
    
    mock_db = AsyncMock() # Мок для объекта базы данных
    mock_db.save_successful_dialog = AsyncMock(return_value=1) # id сохраненного диалога

    await service.send_telegram_dialog_email(
        user_id=user_id,
        username=username,
        contact_info=contact_info,
        dialog_text=dialog_text,
        db=mock_db
    )

    # Проверяем сохранение в БД
    mock_db.save_successful_dialog.assert_called_once_with(
        user_id=user_id,
        username=username,
        contact_info=contact_info,
        messages=dialog_text
    )

    # Проверяем отправку письма
    mock_smtp_server.login.assert_called_once_with(CONFIG.SMTP.USERNAME, CONFIG.SMTP.PASSWORD)
    sent_msg: MIMEMultipart = mock_smtp_server.send_message.call_args[0][0]

    assert sent_msg["Subject"] == f"Новый заказ от пользователя {username}"
    assert sent_msg["To"] == "da1212112@gmail.com" # Захардкожено в методе
    
    html_body = ""
    for part in sent_msg.get_payload():
        if part.get_content_type() == "text/html":
            html_body = part.get_payload(decode=True).decode()
            break
            
    assert f"Клиент:</strong> {user_id} (@{username})" in html_body # Проверяем username с @
    assert f"Имя:</strong> {contact_info['name']}" in html_body
    assert f"Номер:</strong> {contact_info['phone_number']}" in html_body
    assert '<div class="message user">User: Hello there</div>' in html_body
    assert '<div class="message assistant">ChatGPT: Hi! How can I help?</div>' in html_body

@pytest.mark.asyncio
async def test_send_telegram_dialog_email_no_contact_info(service: EmailService, mock_smtp_server):
    # Если contact_info пусто, письмо не должно отправляться
    await service.send_telegram_dialog_email(
        user_id=1, username="user", contact_info={}, dialog_text=[], db=AsyncMock()
    )
    mock_smtp_server.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_send_telegram_dialog_email_no_smtp_credentials(service: EmailService, mock_smtp_server):
    # Модифицируем CONFIG "на лету" для этого теста, чтобы имитировать отсутствие учетных данных
    # Это не лучшая практика, лучше бы передавать конфиг в конструктор сервиса
    # Но раз сервис использует глобальный CONFIG, попробуем так.
    # Важно восстановить значения после теста.
    original_username = CONFIG.SMTP.USERNAME
    original_password = CONFIG.SMTP.PASSWORD
    
    CONFIG.SMTP.USERNAME = None 
    # EmailService читает CONFIG.SMTP.USERNAME и CONFIG.SMTP.PASSWORD в конструкторе.
    # Если мы хотим протестировать логику внутри send_telegram_dialog_email, которая проверяет
    # self.smtp_username и self.smtp_password, то нужно создавать новый экземпляр EmailService
    # уже с измененным CONFIG.
    
    # Создадим новый сервис, который проинициализируется с "испорченным" CONFIG
    with patch.dict(os.environ, {"SMTP_USERNAME": "", "SMTP_PASSWORD": ""}):
        # Чтобы EmailService() подхватил изменения, нужно чтобы CONFIG был перезагружен
        # или чтобы EmailService() читал из os.environ напрямую (что он и делает через CONFIG)
        # Проблема в том, что CONFIG - это синглтон, загруженный при старте.
        # Для чистоты теста, лучше бы EmailService принимал config как аргумент.
        # В текущей структуре, мы можем подменить поля самого объекта CONFIG
        
        # Подменяем поля в уже существующем объекте CONFIG, который использует EmailService
        # Это более грязный способ, но с текущей архитектурой он сработает для теста метода.
        _smtp_config = CONFIG.SMTP
        _original_smtp_user = _smtp_config.USER
        _original_smtp_pass = _smtp_config.PASSWORD
        _original_smtp_username = _smtp_config.USERNAME # Это то, что проверяется в коде

        try:
            _smtp_config.USERNAME = "" # Имитируем отсутствие логина
            _smtp_config.PASSWORD = "" # Имитируем отсутствие пароля
            
            # Создаем новый экземпляр сервиса, который при инициализации возьмет эти подмененные значения из CONFIG.SMTP
            # Это не совсем так, EmailService() берет значения при инициализации.
            # Глобальный email_service уже создан. Нам нужно тестировать его или новый.
            # Если тестируем глобальный, то нужно менять поля CONFIG.SMTP до вызова метода.
            
            # Для теста service, который был создан в фикстуре с нормальным конфигом,
            # нам нужно подменить поля самого экземпляра service или мокнуть CONFIG, который он использует.
            
            # Проще всего для этого теста создать инстанс EmailService здесь,
            # убедившись, что CONFIG.SMTP.USERNAME пустой *до* инициализации.
            
            # Сохраняем текущие значения из CONFIG
            original_smtp_username_in_config = CONFIG.SMTP.USERNAME
            original_smtp_password_in_config = CONFIG.SMTP.PASSWORD
            
            # Подменяем значения в CONFIG
            CONFIG.SMTP.USERNAME = ""
            CONFIG.SMTP.PASSWORD = ""
            
            test_service_instance = EmailService() # Новый экземпляр подхватит измененный CONFIG

            await test_service_instance.send_telegram_dialog_email(
                user_id=1, username="user", contact_info={"name":"test"}, dialog_text=[], db=AsyncMock()
            )
            mock_smtp_server.send_message.assert_not_called()

        finally:
            # Восстанавливаем оригинальные значения в CONFIG, чтобы не влиять на другие тесты
            CONFIG.SMTP.USERNAME = original_smtp_username_in_config
            CONFIG.SMTP.PASSWORD = original_smtp_password_in_config
            
def test_create_email_template(service: EmailService): # не async
    template = service.create_email_template()
    assert isinstance(template, Template)
    # Проверим наличие некоторых ключевых слов, которые должны быть в шаблоне
    test_html = template.substitute(
        user_id="test_uid", username="test_uname", name="test_name", 
        phone="test_phone", dialog="<p>Test Dialog</p>"
    )
    assert "Клиент:" in test_html
    assert "Имя:" in test_html
    assert "Номер:" in test_html
    assert "Диалог с клиентом" in test_html

def test_format_dialog(service: EmailService): # не async
    dialog_text = ["User: Message 1", "Assistant: Message 2", "User: Message 3"]
    formatted = service.format_dialog(dialog_text)
    assert '<div class="message user">User: Message 1</div>' in formatted
    assert '<div class="message assistant">Assistant: Message 2</div>' in formatted
    assert '<div class="message user">User: Message 3</div>' in formatted

# Очистка переменных окружения
def teardown_module(module):
    vars_to_clean = [
        "TELEGRAM_BOT_TOKEN", "OPENAI_API_KEY", "OPENAI_ASSISTANT_ID",
        "REMINDER_ENABLED", "REMINDER_FIRST_REMINDER_TIME", 
        "REMINDER_SECOND_REMINDER_TIME", "REMINDER_FIRST_REMINDER_PROMPT", 
        "REMINDER_SECOND_REMINDER_PROMPT"
    ]
    for var in vars_to_clean:
        if var in os.environ:
            del os.environ[var]
