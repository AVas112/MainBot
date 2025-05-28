import pytest
import asyncio
import os
from datetime import datetime, timedelta 
# Removed timezone import as original database.py uses naive datetimes for strftime

from src.database import Database

# The db fixture is now in conftest.py
FIXED_REGISTRATION_TIMESTAMP_STR = "2023-01-01 10:00:00" # Used by original register_user
MOCK_NOW_DATETIME = datetime(2023, 1, 3, 12, 0, 0) # Naive datetime for mocking


@pytest.mark.asyncio
async def test_database_initialization(tmp_path):
    db_path_str = str(tmp_path / "test_init.db")
    db_instance = Database(db_path=db_path_str)
    assert db_instance.db_path == db_path_str

@pytest.mark.asyncio
async def test_init_db_creates_directory_and_tables(db: Database, tmp_path):
    db_parent_dir = tmp_path
    assert os.path.exists(db_parent_dir)
    assert os.path.exists(db.db_path)

    dialogs_rows = await db.execute_fetch("SELECT name FROM sqlite_master WHERE type='table' AND name='dialogs'")
    assert dialogs_rows is not None and len(dialogs_rows) > 0, "Table 'dialogs' does not seem to exist"
    
    successful_dialogs_rows = await db.execute_fetch("SELECT name FROM sqlite_master WHERE type='table' AND name='successful_dialogs'")
    assert successful_dialogs_rows is not None and len(successful_dialogs_rows) > 0, "Table 'successful_dialogs' does not seem to exist"
    
    user_activity_rows = await db.execute_fetch("SELECT name FROM sqlite_master WHERE type='table' AND name='user_activity'")
    assert user_activity_rows is not None and len(user_activity_rows) > 0, "Table 'user_activity' does not seem to exist"

@pytest.mark.asyncio
async def test_save_and_get_dialog(db: Database):
    user_id = 123
    username = "test_user_dialog"
    message_content_user = "Hello, bot!"
    message_content_assistant = "Hello, user!"

    await db.register_user(user_id, username, FIXED_REGISTRATION_TIMESTAMP_STR)
    # Original register_user inserts an empty system message.
    # Original save_message (user role) calls update_user_activity.

    await db.save_message(user_id, username, message_content_user, 'user')
    dialog = await db.get_dialog(user_id) # Returns list of strings
    
    assert len(dialog) == 2 # System message ("" by register_user) + user message
    # Original get_dialog formats system messages as "ChatGPT: {message}"
    assert dialog[0] == "ChatGPT: " # Empty system message
    assert dialog[1] == f"User: {message_content_user}"

    await db.save_message(user_id, username, message_content_assistant, 'assistant')
    dialog = await db.get_dialog(user_id)
    assert len(dialog) == 3 
    assert dialog[2] == f"ChatGPT: {message_content_assistant}"

@pytest.mark.asyncio
async def test_get_dialog_new_user(db: Database):
    dialog = await db.get_dialog(999) 
    assert len(dialog) == 0

@pytest.mark.asyncio
async def test_save_message_updates_user_activity(db: Database, mocker):
    user_id = 456
    username = "test_user_activity"
    
    await db.register_user(user_id, username, FIXED_REGISTRATION_TIMESTAMP_STR)
    # Original register_user does NOT call update_user_activity.
    # An initial record in user_activity is needed for update_user_activity to successfully UPDATE.
    # The original update_user_activity has INSERT OR UPDATE logic.
    
    mocked_update_activity = mocker.patch.object(db, 'update_user_activity', autospec=True)

    await db.save_message(user_id, username, "Test message", 'user') # This will call update_user_activity
    mocked_update_activity.assert_called_once_with(user_id=user_id)

    mocked_update_activity.reset_mock()
    await db.save_message(user_id, username, "Test response", 'assistant') # This will NOT call update_user_activity
    mocked_update_activity.assert_not_called()


@pytest.mark.asyncio
async def test_save_successful_dialog(db: Database):
    user_id = 789
    username_for_reg = "successful_user_reg"
    username_for_success = "successful_user_success_entry"
    contact_info_dict = {"type": "email", "value": "test@example.com"}
    # messages for save_successful_dialog is a list of dicts as it's directly JSON dumped
    messages_as_dicts = [{"role": "user", "message": "Hello"}, {"role": "assistant", "message": "Hi"}] 
    
    await db.register_user(user_id, username_for_reg, FIXED_REGISTRATION_TIMESTAMP_STR)

    dialog_id = await db.save_successful_dialog(user_id, username_for_success, contact_info_dict, messages_as_dicts)
    assert isinstance(dialog_id, int)
    assert dialog_id > 0

    saved_data_rows = await db.execute_fetch("SELECT user_id, username, contact_info, messages FROM successful_dialogs WHERE id = ?", (dialog_id,))
    assert saved_data_rows is not None and len(saved_data_rows) == 1
    row = saved_data_rows[0]
    assert row[0] == user_id
    assert row[1] == username_for_success
    import json
    assert json.loads(row[2]) == contact_info_dict
    assert json.loads(row[3]) == messages_as_dicts


@pytest.mark.asyncio
async def test_execute_fetch(db: Database):
    user_id = 111
    username = "test_user_fetch"
    await db.register_user(user_id, username, FIXED_REGISTRATION_TIMESTAMP_STR) 

    await db.save_message(user_id, username, "message 1", "user")
    await db.save_message(user_id, username, "response 1", "assistant")

    rows = await db.execute_fetch("SELECT role, message FROM dialogs WHERE user_id = ? ORDER BY timestamp", (user_id,))
    assert len(rows) == 3 
    assert rows[0] == ('system', '') 
    assert rows[1] == ('user', 'message 1')
    assert rows[2] == ('assistant', 'response 1')

@pytest.mark.asyncio
async def test_format_dialog_html(db: Database):
    html_empty = db.format_dialog_html([], "test_user_empty")
    assert "<title>Dialog with test_user_empty</title>" in html_empty
    # Original format_dialog_html does not add a specific paragraph for empty dialogs

    dialog_strings = [ # Original format_dialog_html expects list of strings
        "User: Hello",
        "ChatGPT: Hi there!",
    ]
    html_non_empty = db.format_dialog_html(dialog_strings, "test_user_non_empty")
    assert "<title>Dialog with test_user_non_empty</title>" in html_non_empty
    assert '<div class="message user">User: Hello</div>' in html_non_empty # Adapted assertion
    assert '<div class="message assistant">ChatGPT: Hi there!</div>' in html_non_empty # Adapted assertion
    assert html_non_empty.count('<div class="message') == 2

@pytest.mark.asyncio
async def test_user_registration(db: Database):
    user_id = 101
    username = "testuser"
    
    assert not await db.is_user_registered(user_id)
    await db.register_user(user_id, username, FIXED_REGISTRATION_TIMESTAMP_STR)
    assert await db.is_user_registered(user_id)

    dialog_entries = await db.get_dialog(user_id) 
    assert len(dialog_entries) == 1
    assert dialog_entries[0] == "ChatGPT: " # System message "" by register_user, formatted by get_dialog

    # Original register_user does NOT call update_user_activity.
    activity_rows = await db.execute_fetch("SELECT user_id FROM user_activity WHERE user_id = ?", (user_id,))
    assert len(activity_rows) == 0

@pytest.mark.asyncio
async def test_update_user_activity(db: Database):
    user_id1 = 201
    
    # Call update_user_activity for a new user (tests INSERT part)
    await db.update_user_activity(user_id1) 
    activity1_rows = await db.execute_fetch("SELECT last_activity, first_reminder_sent, second_reminder_sent FROM user_activity WHERE user_id = ?", (user_id1,))
    assert activity1_rows is not None and len(activity1_rows) == 1
    activity1 = activity1_rows[0]
    assert activity1[1] == 0 
    assert activity1[2] == 0 
    last_activity_time1_str = activity1[0]

    # To ensure time difference for the UPDATE part
    # We need a slight delay or ensure the timestamp format has enough resolution
    # For simplicity, we'll assume strptime will show a difference if there is one.
    # A more robust test might involve mocking datetime.now() for more precise control here.
    # However, the original update_user_activity calls datetime.now() internally.

    await db.update_user_activity(user_id1) 
    activity1_updated_rows = await db.execute_fetch("SELECT last_activity FROM user_activity WHERE user_id = ?", (user_id1,))
    assert activity1_updated_rows is not None and len(activity1_updated_rows) == 1
    activity1_updated_str = activity1_updated_rows[0][0]
    
    time_format = "%Y-%m-%d %H:%M:%S" # Original format
    # It's possible they are the same if execution is too fast, so allow greater or equal
    assert datetime.strptime(activity1_updated_str, time_format) >= datetime.strptime(last_activity_time1_str, time_format)


@pytest.mark.asyncio
async def test_get_users_for_reminders(db: Database, mocker):
    user_active_recent = 301
    user_needs_first_reminder = 302
    user_first_reminder_sent = 303
    user_needs_second_reminder = 304
    user_second_reminder_sent = 305
    user_with_successful_dialog = 306

    datetime_mock = mocker.patch('src.database.datetime')
    datetime_mock.now.return_value = MOCK_NOW_DATETIME
    datetime_mock.timedelta = timedelta 

    time_format = "%Y-%m-%d %H:%M:%S"

    # Setup: Register users (does not affect user_activity in original)
    await db.register_user(user_active_recent, "user_active", FIXED_REGISTRATION_TIMESTAMP_STR)
    await db.register_user(user_needs_first_reminder, "user_needs_first", FIXED_REGISTRATION_TIMESTAMP_STR)
    await db.register_user(user_first_reminder_sent, "user_first_sent", FIXED_REGISTRATION_TIMESTAMP_STR)
    await db.register_user(user_needs_second_reminder, "user_needs_second", FIXED_REGISTRATION_TIMESTAMP_STR)
    await db.register_user(user_second_reminder_sent, "user_second_sent", FIXED_REGISTRATION_TIMESTAMP_STR)
    await db.register_user(user_with_successful_dialog, "user_success_diag", FIXED_REGISTRATION_TIMESTAMP_STR)

    # Manually set user_activity states.
    # Using execute_fetch for UPDATE/INSERT. This is not ideal as execute_fetch is for SELECTs and might not commit.
    # However, per instructions, avoiding execute_commit.
    # This test's reliability depends on aiosqlite's behavior with execute_fetch for DML.
    # A more robust test would use `async with aiosqlite.connect(db.db_path) as conn: await conn.execute(...); await conn.commit()`
    
    # Active recent
    await db.execute_fetch("INSERT OR REPLACE INTO user_activity (user_id, last_activity, first_reminder_sent, second_reminder_sent) VALUES (?, ?, 0, 0)", 
                           (user_active_recent, (MOCK_NOW_DATETIME - timedelta(hours=1)).strftime(time_format)))
    # Needs first reminder (inactive 2 days)
    await db.execute_fetch("INSERT OR REPLACE INTO user_activity (user_id, last_activity, first_reminder_sent, second_reminder_sent) VALUES (?, ?, 0, 0)", 
                           (user_needs_first_reminder, (MOCK_NOW_DATETIME - timedelta(days=2)).strftime(time_format)))
    # First reminder sent (inactive 50 hours)
    await db.execute_fetch("INSERT OR REPLACE INTO user_activity (user_id, last_activity, first_reminder_sent, second_reminder_sent) VALUES (?, ?, 1, 0)", 
                           (user_first_reminder_sent, (MOCK_NOW_DATETIME - timedelta(hours=50)).strftime(time_format)))
    # Needs second reminder (inactive 75 hours, first sent)
    await db.execute_fetch("INSERT OR REPLACE INTO user_activity (user_id, last_activity, first_reminder_sent, second_reminder_sent) VALUES (?, ?, 1, 0)", 
                           (user_needs_second_reminder, (MOCK_NOW_DATETIME - timedelta(hours=75)).strftime(time_format)))
    # Second reminder sent (inactive 100 hours, first and second sent)
    await db.execute_fetch("INSERT OR REPLACE INTO user_activity (user_id, last_activity, first_reminder_sent, second_reminder_sent) VALUES (?, ?, 1, 1)", 
                           (user_second_reminder_sent, (MOCK_NOW_DATETIME - timedelta(hours=100)).strftime(time_format)))
    # User with successful dialog (inactive 2 days, but original reminder query doesn't filter this)
    await db.execute_fetch("INSERT OR REPLACE INTO user_activity (user_id, last_activity, first_reminder_sent, second_reminder_sent) VALUES (?, ?, 0, 0)", 
                           (user_with_successful_dialog, (MOCK_NOW_DATETIME - timedelta(days=2)).strftime(time_format)))
    await db.save_successful_dialog(user_with_successful_dialog, "user_s_dialog", {"type":"test"}, ["Test"])


    users_for_first = await db.get_users_for_first_reminder(minutes=24 * 60) # 24 hours
    user_ids_for_first = set(users_for_first)
    
    assert user_needs_first_reminder in user_ids_for_first
    assert user_with_successful_dialog in user_ids_for_first # Original query doesn't filter by successful dialog
    assert user_active_recent not in user_ids_for_first
    assert user_first_reminder_sent not in user_ids_for_first

    users_for_second = await db.get_users_for_second_reminder(minutes=72 * 60) # 72 hours
    user_ids_for_second = set(users_for_second)

    assert user_needs_second_reminder in user_ids_for_second
    assert user_first_reminder_sent not in user_ids_for_second # Inactive 50h < 72h
    assert user_second_reminder_sent not in user_ids_for_second
    assert user_with_successful_dialog not in user_ids_for_second # Because first_reminder_sent is 0

@pytest.mark.asyncio
async def test_mark_reminders_sent(db: Database, mocker): 
    user_id = 401
    await db.register_user(user_id, "reminder_user", FIXED_REGISTRATION_TIMESTAMP_STR)
    # Manually create user_activity record as register_user doesn't
    await db.execute_fetch("INSERT OR REPLACE INTO user_activity (user_id, last_activity, first_reminder_sent, second_reminder_sent) VALUES (?, ?, ?, ?)",
                           (user_id, MOCK_NOW_DATETIME.strftime("%Y-%m-%d %H:%M:%S"), 0, 0))

    await db.mark_first_reminder_sent(user_id)
    activity_rows = await db.execute_fetch("SELECT first_reminder_sent FROM user_activity WHERE user_id = ?", (user_id,))
    assert activity_rows[0][0] == 1 

    await db.mark_second_reminder_sent(user_id)
    activity_rows_second = await db.execute_fetch("SELECT second_reminder_sent FROM user_activity WHERE user_id = ?", (user_id,))
    assert activity_rows_second[0][0] == 1

@pytest.mark.asyncio
async def test_is_successful_dialog(db: Database):
    user_with_success = 501
    user_without_success = 502
    
    await db.register_user(user_with_success, "user_s", FIXED_REGISTRATION_TIMESTAMP_STR)
    await db.register_user(user_without_success, "user_no_s", FIXED_REGISTRATION_TIMESTAMP_STR)

    contact_details = {"email": "success@example.com"}
    # save_successful_dialog expects a list of messages (dicts or strings, it just dumps to JSON)
    dialog_history_for_save = [{"role":"user", "message":"This was a great chat."}] 
    await db.save_successful_dialog(user_with_success, "user_s_dialog", contact_details, dialog_history_for_save)

    assert await db.is_successful_dialog(user_with_success)
    assert not await db.is_successful_dialog(user_without_success)
    assert not await db.is_successful_dialog(999)
