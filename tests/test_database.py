import pytest
import asyncio
import os
import aiosqlite
from datetime import datetime, timedelta, timezone

# Убедимся, что используем тестовую конфигурацию (хотя для database.py это может быть не так критично,
# но хорошая практика - изолировать тестовое окружение)
os.environ["IS_TESTING"] = "1" 
# Для Database важно указать путь к БД. Используем БД в памяти для тестов.
# Чтобы каждый тест был изолирован, лучше создавать новый инстанс Database с новой БД в памяти.

import pytest_asyncio # Import the explicit decorator
from src.database import Database

@pytest_asyncio.fixture # Explicitly use pytest_asyncio.fixture
async def db_instance():
    # Используем уникальное имя для базы данных в памяти для каждого вызова фикстуры,
    # чтобы гарантировать изоляцию между тестами. ':memory:' создает новую БД каждый раз.
    # Однако, если нужно передавать имя файла, можно генерировать уникальное имя файла
    # и удалять его после теста. Для aiosqlite, ':memory:' - лучший вариант.
    db = Database(db_path=":memory:")
    await db.init_db() # Инициализируем таблицы
    return db

@pytest.mark.asyncio
async def test_init_db(db_instance: Database):
    # Проверяем, что таблицы созданы
    async with aiosqlite.connect(db_instance.db_path) as conn:
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dialogs'")
        assert await cursor.fetchone() is not None, "Таблица 'dialogs' не создана"
        
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='successful_dialogs'")
        assert await cursor.fetchone() is not None, "Таблица 'successful_dialogs' не создана"
        
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_activity'")
        assert await cursor.fetchone() is not None, "Таблица 'user_activity' не создана"

@pytest.mark.asyncio
async def test_save_and_get_message(db_instance: Database):
    user_id = 123
    username = "testuser"
    message_text = "Hello, world!"
    role = "user"

    await db_instance.save_message(user_id, username, message_text, role)
    
    dialog = await db_instance.get_dialog(user_id)
    assert len(dialog) == 1
    assert dialog[0] == f"User: {message_text}" # Проверяем форматирование в get_dialog

    # Проверим, что активность пользователя обновилась
    activity = await db_instance.execute_fetch("SELECT * FROM user_activity WHERE user_id = ?", (user_id,))
    assert len(activity) == 1

@pytest.mark.asyncio
async def test_get_dialog_empty(db_instance: Database):
    dialog = await db_instance.get_dialog(999) # Несуществующий user_id
    assert len(dialog) == 0

@pytest.mark.asyncio
async def test_register_user_and_is_registered(db_instance: Database):
    user_id = 456
    username = "newuser"
    first_seen = datetime.now().isoformat()

    assert not await db_instance.is_user_registered(user_id), "Пользователь не должен быть зарегистрирован изначально"
    
    await db_instance.register_user(user_id, username, first_seen)
    assert await db_instance.is_user_registered(user_id), "Пользователь должен быть зарегистрирован"

    # Проверим, что системное сообщение было добавлено
    dialog = await db_instance.get_dialog(user_id)
    assert len(dialog) == 1
    assert dialog[0] == "ChatGPT: " # Системное сообщение от "assistant", но get_dialog форматирует как ChatGPT

@pytest.mark.asyncio
async def test_update_user_activity(db_instance: Database):
    user_id = 789
    current_time_dt = datetime.now()
    
    # Сначала сохраним сообщение, чтобы создать запись в user_activity
    await db_instance.save_message(user_id, "activity_user", "initial message", "user")
    
    # Получаем время первой активности
    initial_activity_row = await db_instance.execute_fetch("SELECT last_activity FROM user_activity WHERE user_id = ?", (user_id,))
    initial_activity_time = datetime.strptime(initial_activity_row[0][0], "%Y-%m-%d %H:%M:%S")
    
    # Ждем немного, чтобы время гарантированно отличалось
    await asyncio.sleep(0.01) 
    
    await db_instance.update_user_activity(user_id)
    
    updated_activity_row = await db_instance.execute_fetch("SELECT last_activity FROM user_activity WHERE user_id = ?", (user_id,))
    updated_activity_time = datetime.strptime(updated_activity_row[0][0], "%Y-%m-%d %H:%M:%S")
    
    assert updated_activity_time > initial_activity_time

@pytest.mark.asyncio
async def test_get_users_for_reminders(db_instance: Database):
    user_active_id = 101
    user_inactive_first_reminder_id = 102
    user_inactive_second_reminder_id = 103
    user_reminded_first_id = 104 # Уже получил первое напоминание

    now = datetime.now()
    time_format = "%Y-%m-%d %H:%M:%S"

    # Активный пользователь
    await db_instance.update_user_activity(user_active_id)

    # Пользователь для первого напоминания (неактивен 10 минут)
    ten_minutes_ago = (now - timedelta(minutes=10)).strftime(time_format)
    async with aiosqlite.connect(db_instance.db_path) as conn:
        await conn.execute(
            "INSERT INTO user_activity (user_id, last_activity, first_reminder_sent, second_reminder_sent) VALUES (?, ?, 0, 0)",
            (user_inactive_first_reminder_id, ten_minutes_ago)
        )
        await conn.commit()

    # Пользователь для второго напоминания (неактивен 20 минут, первое напоминание отправлено)
    twenty_minutes_ago = (now - timedelta(minutes=20)).strftime(time_format)
    async with aiosqlite.connect(db_instance.db_path) as conn:
        await conn.execute(
            "INSERT INTO user_activity (user_id, last_activity, first_reminder_sent, second_reminder_sent) VALUES (?, ?, 1, 0)",
            (user_inactive_second_reminder_id, twenty_minutes_ago)
        )
        await conn.commit()
    
    # Пользователь, которому уже отправлено первое напоминание (недавно)
    five_minutes_ago = (now - timedelta(minutes=5)).strftime(time_format) # неактивен 5 минут, но первое уже отправлено
    async with aiosqlite.connect(db_instance.db_path) as conn:
        await conn.execute(
            "INSERT INTO user_activity (user_id, last_activity, first_reminder_sent, second_reminder_sent) VALUES (?, ?, 1, 0)",
            (user_reminded_first_id, five_minutes_ago)
        )
        await conn.commit()


    users_for_first = await db_instance.get_users_for_first_reminder(minutes=5) # Порог 5 минут
    assert user_inactive_first_reminder_id in users_for_first
    assert user_active_id not in users_for_first
    assert user_inactive_second_reminder_id not in users_for_first # т.к. first_reminder_sent = 1
    assert user_reminded_first_id not in users_for_first # т.к. first_reminder_sent = 1

    users_for_second = await db_instance.get_users_for_second_reminder(minutes=15) # Порог 15 минут
    assert user_inactive_second_reminder_id in users_for_second
    assert user_active_id not in users_for_second
    assert user_inactive_first_reminder_id not in users_for_second # т.к. first_reminder_sent = 0
    assert user_reminded_first_id not in users_for_second # т.к. last_activity не достаточно старая

@pytest.mark.asyncio
async def test_mark_reminders_sent(db_instance: Database):
    user_id = 201
    await db_instance.update_user_activity(user_id) # Создаем запись

    await db_instance.mark_first_reminder_sent(user_id)
    activity = await db_instance.execute_fetch("SELECT first_reminder_sent FROM user_activity WHERE user_id = ?", (user_id,))
    assert activity[0][0] == 1

    await db_instance.mark_second_reminder_sent(user_id)
    activity = await db_instance.execute_fetch("SELECT second_reminder_sent FROM user_activity WHERE user_id = ?", (user_id,))
    assert activity[0][0] == 1

@pytest.mark.asyncio
async def test_save_and_is_successful_dialog(db_instance: Database):
    user_id = 301
    username = "successful_user"
    contact_info = {"name": "Test", "phone": "12345"}
    messages = ["User: Hi", "ChatGPT: Hello"]

    assert not await db_instance.is_successful_dialog(user_id)
    
    dialog_id = await db_instance.save_successful_dialog(user_id, username, contact_info, messages)
    assert dialog_id is not None
    assert await db_instance.is_successful_dialog(user_id)

    # Проверим содержимое
    saved_dialog = await db_instance.execute_fetch("SELECT * FROM successful_dialogs WHERE user_id = ?", (user_id,))
    assert len(saved_dialog) == 1
    assert saved_dialog[0][1] == user_id
    assert saved_dialog[0][2] == username
    assert saved_dialog[0][3] == '{"name": "Test", "phone": "12345"}' # JSON строка
    assert saved_dialog[0][4] == '["User: Hi", "ChatGPT: Hello"]'   # JSON строка

@pytest.mark.asyncio
async def test_execute_fetch(db_instance: Database):
    user_id = 401
    await db_instance.save_message(user_id, "fetch_user", "test message", "user")
    
    result = await db_instance.execute_fetch("SELECT username FROM dialogs WHERE user_id = ?", (user_id,))
    assert len(result) == 1
    assert result[0][0] == "fetch_user"

def test_format_dialog_html(db_instance: Database): # Этот метод не async
    dialog_lines = ["User: Hello", "Assistant: Hi there!"]
    username = "html_user"
    html = db_instance.format_dialog_html(dialog_lines, username)
    
    assert "<!DOCTYPE html>" in html
    assert f"<title>Dialog with {username}</title>" in html
    assert '<div class="message user">User: Hello</div>' in html
    assert '<div class="message assistant">Assistant: Hi there!</div>' in html
