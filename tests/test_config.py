import os
import pytest
from dotenv import load_dotenv

load_dotenv(override=True) # Важно вызвать до импорта CONFIG

# Устанавливаем переменные окружения, которые могут отсутствовать в .env, но нужны для инициализации CONFIG
os.environ.setdefault("REMINDER_ENABLED", "True")
os.environ.setdefault("REMINDER_FIRST_REMINDER_TIME", "60")
os.environ.setdefault("REMINDER_SECOND_REMINDER_TIME", "120")
os.environ.setdefault("REMINDER_FIRST_REMINDER_PROMPT", "First reminder prompt for {minutes} minutes")
os.environ.setdefault("REMINDER_SECOND_REMINDER_PROMPT", "Second reminder prompt for {minutes} minutes")
os.environ.setdefault("USE_PROXY", "False") # Для ProxyConfig
os.environ.setdefault("PROXY_HOST", "test_host") # Чтобы ProxyConfig не падал, если USE_PROXY=True где-то
os.environ.setdefault("PROXY_PORT", "0")
os.environ.setdefault("PROXY_USERNAME", "test_user")
os.environ.setdefault("PROXY_PASSWORD", "test_pass")
# Добавьте другие минимально необходимые переменные для полной инициализации CONFIG, если требуется
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake_token_for_config_test")
os.environ.setdefault("TELEGRAM_ADMIN_CHAT_ID", "-1")
os.environ.setdefault("OPENAI_API_KEY", "fake_api_key_for_config_test")
os.environ.setdefault("OPENAI_ASSISTANT_ID", "fake_assistant_id_for_config_test")
os.environ.setdefault("SMTP_SERVER", "fake_server")
os.environ.setdefault("SMTP_PORT", "0")
os.environ.setdefault("SMTP_USERNAME", "fake_smtp_user")
os.environ.setdefault("SMTP_PASSWORD", "fake_smtp_pass")
os.environ.setdefault("SMTP_NOTIFICATION_EMAIL", "fake_email")
os.environ.setdefault("WEB_UI_BASE_URL", "http://fakeurl")
os.environ.setdefault("REPORT_HOUR", "0")
os.environ.setdefault("REPORT_MINUTE", "0")


from src.config.config import (
    CONFIG,
    TGBotConfig, # ИСПРАВЛЕНО: TelegramConfig -> TGBotConfig
    OpenAIConfig,
    SMTPConfig,
    WebUIConfig,
    ProxyConfig,
    ReportConfig, # Убедимся, что ReportConfig импортируется, если он есть
    ReminderConfig
)

def test_load_telegram_config():
    load_dotenv(override=True) # Перезагружаем .env для этого теста
    # Устанавливаем переменные, специфичные для этого теста, если они отличаются от глобальных setdefault
    os.environ["TELEGRAM_BOT_TOKEN"] = os.getenv("TELEGRAM_BOT_TOKEN", "default_token_in_test")
    os.environ["TELEGRAM_ADMIN_CHAT_ID"] = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "-100")

    telegram_config = TGBotConfig() # ИСПРАВЛЕНО
    assert telegram_config.BOT_TOKEN == os.getenv("TELEGRAM_BOT_TOKEN")
    assert telegram_config.ADMIN_CHAT_ID == int(os.getenv("TELEGRAM_ADMIN_CHAT_ID"))

def test_load_openai_config():
    load_dotenv(override=True)
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "default_api_key_in_test")
    os.environ["OPENAI_ASSISTANT_ID"] = os.getenv("OPENAI_ASSISTANT_ID", "default_assistant_id_in_test")

    openai_config = OpenAIConfig()
    assert openai_config.API_KEY == os.getenv("OPENAI_API_KEY")
    assert openai_config.ASSISTANT_ID == os.getenv("OPENAI_ASSISTANT_ID")

def test_load_smtp_config():
    load_dotenv(override=True)
    os.environ["SMTP_USERNAME"] = os.getenv("SMTP_USERNAME", "default_smtp_user")
    os.environ["SMTP_PASSWORD"] = os.getenv("SMTP_PASSWORD", "default_smtp_pass")
    os.environ["SMTP_SERVER"] = os.getenv("SMTP_SERVER", "default_smtp_server")
    os.environ["SMTP_PORT"] = os.getenv("SMTP_PORT", "5870") # другое значение по умолчанию для теста
    os.environ["SMTP_NOTIFICATION_EMAIL"] = os.getenv("SMTP_NOTIFICATION_EMAIL", "default_notify_email")

    smtp_config = SMTPConfig()
    assert smtp_config.USERNAME == os.getenv("SMTP_USERNAME") # ИСПРАВЛЕНО
    assert smtp_config.PASSWORD == os.getenv("SMTP_PASSWORD")
    assert smtp_config.SERVER == os.getenv("SMTP_SERVER")
    assert smtp_config.PORT == int(os.getenv("SMTP_PORT"))
    assert smtp_config.NOTIFICATION_EMAIL == os.getenv("SMTP_NOTIFICATION_EMAIL")


def test_load_web_ui_config():
    load_dotenv(override=True)
    os.environ["WEB_UI_BASE_URL"] = os.getenv("WEB_UI_BASE_URL", "http://default_webui")
    web_ui_config = WebUIConfig()
    assert web_ui_config.BASE_URL == os.getenv("WEB_UI_BASE_URL")

def test_load_proxy_config():
    load_dotenv(override=True)
    # Значения по умолчанию для теста, если не переопределены в .env
    os.environ.setdefault("PROXY_HOST", "default_proxy_host")
    os.environ.setdefault("PROXY_PORT", "8000")
    os.environ.setdefault("PROXY_USERNAME", "default_proxy_user")
    os.environ.setdefault("PROXY_PASSWORD", "default_proxy_pass")
    
    # Тест для случая, когда прокси выключен (USE_PROXY не установлен или False)
    os.environ["USE_PROXY"] = "False"
    proxy_config_disabled = ProxyConfig() # Создаем новый экземпляр
    assert proxy_config_disabled.HOST == os.getenv("PROXY_HOST")
    assert proxy_config_disabled.PORT == int(os.getenv("PROXY_PORT"))
    assert proxy_config_disabled.USERNAME == os.getenv("PROXY_USERNAME")
    assert proxy_config_disabled.PASSWORD == os.getenv("PROXY_PASSWORD")
    assert proxy_config_disabled.USE_PROXY is False # ИСПРАВЛЕНО

    # Тест для случая, когда прокси включен
    os.environ["USE_PROXY"] = "True"
    proxy_config_enabled = ProxyConfig() # Создаем новый экземпляр
    assert proxy_config_enabled.USE_PROXY is True # ИСПРАВЛЕНО
    
    # Очищаем USE_PROXY, чтобы не влиять на другие тесты, если он был установлен только здесь
    del os.environ["USE_PROXY"]


def test_load_report_config():
    load_dotenv(override=True)
    os.environ["REPORT_HOUR"] = os.getenv("REPORT_HOUR", "10") # другое значение по умолчанию для теста
    os.environ["REPORT_MINUTE"] = os.getenv("REPORT_MINUTE", "30")

    report_config = ReportConfig()
    assert report_config.HOUR == int(os.getenv("REPORT_HOUR"))
    assert report_config.MINUTE == int(os.getenv("REPORT_MINUTE"))

def test_load_reminder_config():
    load_dotenv(override=True)
    # Значения по умолчанию для этого теста
    os.environ["REMINDER_ENABLED"] = os.getenv("REMINDER_ENABLED", "True")
    os.environ["REMINDER_FIRST_REMINDER_TIME"] = os.getenv("REMINDER_FIRST_REMINDER_TIME", "50")
    os.environ["REMINDER_SECOND_REMINDER_TIME"] = os.getenv("REMINDER_SECOND_REMINDER_TIME", "110")
    os.environ["REMINDER_FIRST_REMINDER_PROMPT"] = os.getenv("REMINDER_FIRST_REMINDER_PROMPT", "Test prompt 1 {minutes}")
    os.environ["REMINDER_SECOND_REMINDER_PROMPT"] = os.getenv("REMINDER_SECOND_REMINDER_PROMPT", "Test prompt 2 {minutes}")

    reminder_config = ReminderConfig()

    assert reminder_config.ENABLED == (os.getenv("REMINDER_ENABLED").lower() == "true")
    assert reminder_config.FIRST_REMINDER_TIME == int(os.getenv("REMINDER_FIRST_REMINDER_TIME"))
    assert reminder_config.SECOND_REMINDER_TIME == int(os.getenv("REMINDER_SECOND_REMINDER_TIME"))
    assert reminder_config.FIRST_REMINDER_PROMPT == os.getenv("REMINDER_FIRST_REMINDER_PROMPT")
    assert reminder_config.SECOND_REMINDER_PROMPT == os.getenv("REMINDER_SECOND_REMINDER_PROMPT")


def test_global_config_object():
    # Этот тест проверяет глобальный объект CONFIG, который был импортирован один раз.
    # Его значения зависят от того, что было в .env и os.environ на момент первого импорта src.config.config.
    # load_dotenv(override=True) в начале файла должен был загрузить .env до импорта.
    # os.environ.setdefault в начале файла должен был установить значения по умолчанию.
    
    # Для большей надежности, можно было бы создать функцию, которая возвращает новый CONFIG
    # или перезагружает модуль, но это усложнит тест.
    # Проверяем текущее состояние глобального CONFIG.
    
    assert CONFIG.TELEGRAM.BOT_TOKEN == os.getenv("TELEGRAM_BOT_TOKEN")
    assert CONFIG.OPENAI.API_KEY == os.getenv("OPENAI_API_KEY")
    assert CONFIG.SMTP.SERVER == os.getenv("SMTP_SERVER")
    assert CONFIG.WEB_UI.BASE_URL == os.getenv("WEB_UI_BASE_URL")
    assert CONFIG.PROXY.HOST == os.getenv("PROXY_HOST")
    assert CONFIG.PROXY.USE_PROXY == (os.getenv("USE_PROXY", "False").lower() == "true") # ИСПРАВЛЕНО
    assert CONFIG.REPORT.HOUR == int(os.getenv("REPORT_HOUR"))
    assert CONFIG.REMINDER.ENABLED == (os.getenv("REMINDER_ENABLED", "False").lower() == "true")

# teardown_module не нужен, если мы используем override=True и setdefault правильно,
# и если тесты не изменяют os.environ таким образом, чтобы это влияло на другие файлы тестов.
# Но для чистоты можно оставить очистку тех переменных, которые мы точно меняем в os.environ.
def teardown_module(module):
    vars_to_clean = [
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_ADMIN_CHAT_ID", 
        "OPENAI_API_KEY", "OPENAI_ASSISTANT_ID",
        "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_SERVER", "SMTP_PORT", "SMTP_NOTIFICATION_EMAIL",
        "WEB_UI_BASE_URL",
        "USE_PROXY", "PROXY_HOST", "PROXY_PORT", "PROXY_USERNAME", "PROXY_PASSWORD",
        "REPORT_HOUR", "REPORT_MINUTE",
        "REMINDER_ENABLED", "REMINDER_FIRST_REMINDER_TIME", "REMINDER_SECOND_REMINDER_TIME",
        "REMINDER_FIRST_REMINDER_PROMPT", "REMINDER_SECOND_REMINDER_PROMPT"
    ]
    for var in vars_to_clean:
        if var in os.environ:
            # Удаляем только если переменная была установлена именно в os.environ,
            # а не просто присутствовала (например, из системного окружения).
            # Это сложно отследить без сохранения исходного состояния.
            # Безопаснее просто убедиться, что load_dotenv(override=True) используется в каждом тесте,
            # или что тесты не зависят от глобального состояния os.environ между собой.
            # Для простоты, пока оставим так.
            pass
