import pytest
import asyncio
import os
from datetime import datetime, timedelta, timezone
from src.database import Database

# The db fixture is now in conftest.py

@pytest.mark.asyncio
async def test_database_initialization(tmp_path):
    db_path_str = str(tmp_path / "test_init.db")
    db_instance = Database(db_path=db_path_str)
    assert db_instance.db_path == db_path_str

@pytest.mark.asyncio
async def test_init_db_creates_directory_and_tables(db: Database, tmp_path):
    # Directory creation is implicitly tested by the db fixture's tmp_path usage
    db_parent_dir = tmp_path
    assert os.path.exists(db_parent_dir)

    # Check if the database file itself was created
    assert os.path.exists(db.db_path)

    # Check table creation by trying to select from them
    dialogs_rows = await db.execute_fetch("SELECT name FROM sqlite_master WHERE type='table' AND name='dialogs'")
    assert dialogs_rows is not None and len(dialogs_rows) > 0, "Table 'dialogs' does not seem to exist"
    
    successful_dialogs_rows = await db.execute_fetch("SELECT name FROM sqlite_master WHERE type='table' AND name='successful_dialogs'")
    assert successful_dialogs_rows is not None and len(successful_dialogs_rows) > 0, "Table 'successful_dialogs' does not seem to exist"
    
    user_activity_rows = await db.execute_fetch("SELECT name FROM sqlite_master WHERE type='table' AND name='user_activity'")
    assert user_activity_rows is not None and len(user_activity_rows) > 0, "Table 'user_activity' does not seem to exist"
    # 'users' table is not explicitly created by init_db; user info is in 'dialogs' and 'user_activity'

@pytest.mark.asyncio
async def test_save_and_get_dialog(db: Database):
    user_id = 123
    username = "test_user_dialog"
    message_content = "Hello, bot!"
    await db.save_message(user_id, username, message_content, 'user')

    dialog = await db.get_dialog(user_id)
    assert len(dialog) == 1
    assert dialog[0]['role'] == 'user'
    assert dialog[0]['message'] == message_content # Changed 'content' to 'message'

    await db.save_message(user_id, username, "Hello, user!", 'assistant')
    dialog = await db.get_dialog(user_id)
    assert len(dialog) == 2
    assert dialog[1]['role'] == 'assistant'
    assert dialog[1]['message'] == "Hello, user!" # Changed 'content' to 'message'

@pytest.mark.asyncio
async def test_get_dialog_new_user(db: Database):
    dialog = await db.get_dialog(999) # Non-existent user
    assert len(dialog) == 0

@pytest.mark.asyncio
async def test_save_message_updates_user_activity(db: Database, mocker):
    user_id = 456
    username = "test_user_activity"
    # Ensure user is registered before saving messages that might trigger activity updates
    # Use a fixed timestamp for predictability
    fixed_timestamp = "2023-01-01T12:00:00+00:00"
    await db.register_user(user_id, username, fixed_timestamp)

    mocker.patch.object(db, 'update_user_activity')
    await db.save_message(user_id, username, "Test message", 'user')
    # update_user_activity is called inside save_message with user_id as a keyword argument
    db.update_user_activity.assert_called_once_with(user_id=user_id)


    # Check that it's not called for assistant messages
    db.update_user_activity.reset_mock()
    await db.save_message(user_id, username, "Test response", 'assistant')
    db.update_user_activity.assert_not_called()


@pytest.mark.asyncio
async def test_save_successful_dialog(db: Database):
    user_id = 789
    username_for_dialog = "successful_user_dialog" # Different from username in successful_dialogs table
    # contact_info is expected as a dict by db.save_successful_dialog
    contact_info_dict = {"type": "username", "value": "test_contact_value"}
    messages_list = [{"role": "user", "message": "Hello"}, {"role": "assistant", "message": "Hi"}]
    
    # Ensure user is registered (creates a system message in dialogs and an activity entry)
    fixed_timestamp = "2023-01-01T12:00:00+00:00"
    await db.register_user(user_id, "successful_user_registration", fixed_timestamp)

    # username in save_successful_dialog is for the successful_dialogs table, can be different from registration username.
    dialog_id = await db.save_successful_dialog(user_id, username_for_dialog, contact_info_dict, messages_list)
    assert isinstance(dialog_id, int)
    assert dialog_id > 0

    # Verify the saved data directly from successful_dialogs table
    # Schema: user_id, username, contact_info (TEXT storing JSON), messages (TEXT storing JSON)
    saved_data_rows = await db.execute_fetch("SELECT user_id, username, contact_info, messages FROM successful_dialogs WHERE id = ?", (dialog_id,))
    assert saved_data_rows is not None and len(saved_data_rows) == 1
    row = saved_data_rows[0]
    assert row[0] == user_id
    assert row[1] == username_for_dialog 
    import json
    assert json.loads(row[2]) == contact_info_dict
    assert json.loads(row[3]) == messages_list

@pytest.mark.asyncio
async def test_execute_fetch(db: Database):
    user_id = 111
    username = "test_user_fetch"
    fixed_timestamp = "2023-01-01T12:00:00+00:00"
    await db.register_user(user_id, username, fixed_timestamp)

    await db.save_message(user_id, username, "message 1", "user")
    await db.save_message(user_id, username, "response 1", "assistant")

    # Querying 'message' column instead of 'content'
    # register_user adds a system message, so expect 3 messages now
    rows = await db.execute_fetch("SELECT role, message FROM dialogs WHERE user_id = ?", (user_id,))
    assert len(rows) == 3 
    assert rows[0] == ('system', 'User registered.')
    assert rows[1] == ('user', 'message 1')
    assert rows[2] == ('assistant', 'response 1')

    rows_empty = await db.execute_fetch("SELECT role, message FROM dialogs WHERE user_id = ?", (9999,))
    assert len(rows_empty) == 0

    count_rows = await db.execute_fetch("SELECT COUNT(*) FROM dialogs WHERE user_id = ?", (user_id,))
    assert count_rows is not None and len(count_rows) == 1
    count_row = count_rows[0]
    assert count_row[0] == 3 # 1 system message from register_user + 2 saved messages

@pytest.mark.asyncio
async def test_format_dialog_html(db: Database):
    # format_dialog_html expects a list of dicts like [{'role': 'user', 'message': 'text'}]
    html_empty = db.format_dialog_html([], "test_user_empty") # Pass empty list of dicts
    assert "<title>Dialog with test_user_empty</title>" in html_empty
    assert "<p>No messages in this dialog yet.</p>" in html_empty

    dialog_entries = [
        {'role': 'user', 'message': 'Hello'},
        {'role': 'assistant', 'message': 'Hi there!'},
        {'role': 'system', 'message': 'User registered.'} # Example system message
    ]
    html_non_empty = db.format_dialog_html(dialog_entries, "test_user_non_empty")
    assert "<title>Dialog with test_user_non_empty</title>" in html_non_empty
    assert '<div class="message user-message"><strong>User:</strong> Hello</div>' in html_non_empty
    assert '<div class="message assistant-message"><strong>Assistant:</strong> Hi there!</div>' in html_non_empty
    assert '<div class="message system-message"><strong>System:</strong> User registered.</div>' in html_non_empty
    assert html_non_empty.count('<div class="message') == 3

@pytest.mark.asyncio
async def test_user_registration(db: Database):
    user_id = 101
    username = "testuser"
    fixed_timestamp = "2023-01-01T12:00:00+00:00"

    assert not await db.is_user_registered(user_id) # Checks dialogs table
    await db.register_user(user_id, username, fixed_timestamp)
    assert await db.is_user_registered(user_id)

    # Verify the system message in dialogs table
    dialog_entries = await db.get_dialog(user_id)
    assert len(dialog_entries) == 1
    system_message_entry = dialog_entries[0]
    assert system_message_entry['role'] == 'system'
    assert system_message_entry['message'] == "User registered."
    # To check timestamp, we'd need to query dialogs table directly for timestamp column.
    # For simplicity, we assume register_user sets it correctly.

    # Check user_activity table entry
    activity_rows = await db.execute_fetch("SELECT user_id, last_activity FROM user_activity WHERE user_id = ?", (user_id,))
    assert activity_rows is not None and len(activity_rows) == 1
    # last_activity is set by update_user_activity called within register_user

    # Test re-registration (should not duplicate, but update_user_activity will be called)
    new_fixed_timestamp = "2023-01-01T12:05:00+00:00"
    # The current register_user implementation would insert another "system" message.
    # This might or might not be desired. For this test, we just check if it runs.
    await db.register_user(user_id, "new_username_reg", new_fixed_timestamp)
    
    dialog_entries_updated = await db.get_dialog(user_id)
    # Expecting two system messages if register_user is called twice without specific upsert logic for the system message itself.
    assert len(dialog_entries_updated) == 2 
    assert dialog_entries_updated[1]['message'] == "User registered."
    assert dialog_entries_updated[1]['role'] == 'system'


@pytest.mark.asyncio
async def test_is_user_registered_non_existent(db: Database):
    assert not await db.is_user_registered(9999)

@pytest.mark.asyncio
async def test_update_user_activity(db: Database):
    user_id1 = 201
    user_id2 = 202
    username1 = "activity_user1" # Username is not used by update_user_activity
    username2 = "activity_user2"
    fixed_timestamp = "2023-01-01T12:00:00+00:00"

    # Register users first to ensure they exist for activity tracking
    await db.register_user(user_id1, username1, fixed_timestamp)
    await db.register_user(user_id2, username2, fixed_timestamp)

    # update_user_activity is called by register_user, so activity already exists.
    # Call it again to test its direct effect.
    await db.update_user_activity(user_id1) 
    activity1_rows = await db.execute_fetch("SELECT last_activity, first_reminder_sent, second_reminder_sent FROM user_activity WHERE user_id = ?", (user_id1,))
    assert activity1_rows is not None and len(activity1_rows) == 1
    activity1 = activity1_rows[0]
    assert activity1[1] == 0 # first_reminder_sent
    assert activity1[2] == 0 # second_reminder_sent
    last_activity_time1_iso = activity1[0] # last_activity

    await asyncio.sleep(0.01) # Ensure time difference for next update

    await db.update_user_activity(user_id1) # Call with only user_id
    activity1_updated_rows = await db.execute_fetch("SELECT last_activity FROM user_activity WHERE user_id = ?", (user_id1,))
    assert activity1_updated_rows is not None and len(activity1_updated_rows) == 1
    activity1_updated_iso = activity1_updated_rows[0][0]
    assert activity1_updated_iso > last_activity_time1_iso

    await db.update_user_activity(user_id2) # Call with only user_id
    activity2_rows = await db.execute_fetch("SELECT last_activity FROM user_activity WHERE user_id = ?", (user_id2,))
    assert activity2_rows is not None and len(activity2_rows) == 1
    assert activity2_rows[0][0] is not None # last_activity should be set

@pytest.mark.asyncio
async def test_get_users_for_reminders(db: Database, mocker): # Added mocker
    user_active_recent = 301
    user_needs_first_reminder = 302
    user_first_reminder_sent_recently = 303
    user_needs_second_reminder = 304
    user_second_reminder_sent = 305
    user_successful_dialog_active = 306
    user_successful_dialog_inactive = 307
    
    # Use a fixed reference time for predictable test setup
    fixed_registration_time = "2023-01-01T10:00:00+00:00"
    # This will be the mocked 'current time' for the SUT methods
    now_utc_for_test = datetime(2023, 1, 3, 12, 0, 0, tzinfo=timezone.utc)


    # Register all users
    users_to_register = {
        user_active_recent: "user_active_recent",
        user_needs_first_reminder: "user_needs_first_reminder",
        user_first_reminder_sent_recently: "user_first_reminder_sent_recently",
        user_needs_second_reminder: "user_needs_second_reminder",
        user_second_reminder_sent: "user_second_reminder_sent",
        user_successful_dialog_active: "user_successful_dialog_active",
        user_successful_dialog_inactive: "user_successful_dialog_inactive"
    }
    for uid, uname in users_to_register.items():
        await db.register_user(uid, uname, fixed_registration_time) # register_user also calls update_user_activity

    # Manually set user_activity states using INSERT OR REPLACE for clarity and full control after registration
    activity_setup_query = "INSERT OR REPLACE INTO user_activity (user_id, last_activity, first_reminder_sent, second_reminder_sent) VALUES (?, ?, ?, ?)"

    # Active recent: activity 1 hour ago
    await db.execute_commit(activity_setup_query, (user_active_recent, (now_utc_for_test - timedelta(hours=1)).isoformat(), 0, 0))
    # Needs first reminder: activity 2 days ago (more pronounced)
    await db.execute_commit(activity_setup_query, (user_needs_first_reminder, (now_utc_for_test - timedelta(days=2)).isoformat(), 0, 0))
    # First reminder sent (recently): activity 50h ago, first_reminder_sent = 1
    await db.execute_commit(activity_setup_query, (user_first_reminder_sent_recently, (now_utc_for_test - timedelta(hours=50)).isoformat(), 1, 0))
    # Needs second reminder: activity 75h ago, first_reminder_sent = 1
    await db.execute_commit(activity_setup_query, (user_needs_second_reminder, (now_utc_for_test - timedelta(hours=75)).isoformat(), 1, 0))
    # Second reminder sent: activity 100h ago, first_reminder_sent = 1, second_reminder_sent = 1
    await db.execute_commit(activity_setup_query, (user_second_reminder_sent, (now_utc_for_test - timedelta(hours=100)).isoformat(), 1, 1))
    
    # User successful dialog (active): activity 1h ago
    await db.execute_commit(activity_setup_query, (user_successful_dialog_active, (now_utc_for_test - timedelta(hours=1)).isoformat(), 0, 0))
    await db.save_successful_dialog(user_successful_dialog_active, "user_sd_active", {"type":"email", "value":"active@test.com"}, [{"role":"user", "message":"test"}])
    # User successful dialog (inactive): activity 25h ago
    await db.execute_commit(activity_setup_query, (user_successful_dialog_inactive, (now_utc_for_test - timedelta(hours=25)).isoformat(), 0, 0))
    await db.save_successful_dialog(user_successful_dialog_inactive, "user_sd_inactive", {"type":"email", "value":"inactive@test.com"}, [{"role":"user", "message":"test"}])

    # Mock datetime.now() in reminder methods to control "current time" for query thresholds
    # This requires database methods to use a consistent way to get 'now', ideally passed in or mocked.
    # For now, we rely on the fact that our test setup times are relative to a fixed 'now_utc_for_test'
    # and the reminder methods in database.py use datetime.now(timezone.utc).
    # This might lead to slight inaccuracies if test execution takes too long. # No longer, with mocking.
    # A more robust solution would involve patching datetime.now within the Database methods. # Doing this now.
    
    # Reminder methods in Database use minutes.
    # Patch datetime.now used by the database methods
    datetime_mock = mocker.patch('src.database.datetime')
    # Configure the mock for datetime.now() called within src.database
    datetime_mock.now.return_value = now_utc_for_test
    # If src.database.datetime.timezone.utc is used, ensure it's available
    datetime_mock.timezone = timezone # Expose the original timezone object via the mock


    # Test get_users_for_first_reminder (e.g., inactive for > 24 hours = 1440 minutes)
    users_for_first = await db.get_users_for_first_reminder(minutes=24 * 60)
    user_ids_for_first = {u for u in users_for_first}

    assert user_needs_first_reminder in user_ids_for_first # Inactive 25h
    assert user_active_recent not in user_ids_for_first # Active 1h ago
    assert user_first_reminder_sent_recently not in user_ids_for_first # Already had first reminder
    assert user_needs_second_reminder not in user_ids_for_first # Already had first reminder
    assert user_second_reminder_sent not in user_ids_for_first # Already had both reminders
    assert user_successful_dialog_active not in user_ids_for_first # Has successful dialog
    assert user_successful_dialog_inactive not in user_ids_for_first # Has successful dialog

    # Test get_users_for_second_reminder (e.g., inactive for > 48 hours, and first reminder sent)
    # This depends on how 'minutes' is interpreted in get_users_for_second_reminder.
    # Current DB code: last_activity < (now - minutes_arg) AND first_reminder_sent = 1
    # This means if a user got first reminder and is still inactive for 'minutes_arg', they get second.
    users_for_second = await db.get_users_for_second_reminder(minutes=72 * 60) # Check for users inactive > 72 hours
    user_ids_for_second = {u for u in users_for_second}

    assert user_needs_second_reminder in user_ids_for_second # Inactive 75h, first_reminder_sent=1
    assert user_active_recent not in user_ids_for_second
    assert user_needs_first_reminder not in user_ids_for_second # first_reminder_sent=0
    assert user_first_reminder_sent_recently not in user_ids_for_second # Inactive only 50h, less than 72h threshold
    assert user_second_reminder_sent not in user_ids_for_second # second_reminder_sent=1
    assert user_successful_dialog_active not in user_ids_for_second
    assert user_successful_dialog_inactive not in user_ids_for_second

@pytest.mark.asyncio
async def test_mark_reminders_sent(db: Database, mocker): # Added mocker
    user_id = 401
    username = "reminder_user"
    fixed_timestamp = "2023-01-01T12:00:00+00:00"
    await db.register_user(user_id, username, fixed_timestamp) # This calls update_user_activity

    await db.mark_first_reminder_sent(user_id)
    # user_activity table does not have first_reminder_sent_time column in the provided schema
    activity_rows = await db.execute_fetch("SELECT first_reminder_sent FROM user_activity WHERE user_id = ?", (user_id,))
    assert activity_rows is not None and len(activity_rows) == 1
    activity = activity_rows[0]
    assert activity[0] == 1 # first_reminder_sent is True (1)
    # assert activity[1] is not None # No first_reminder_sent_time column

    await db.mark_second_reminder_sent(user_id)
    # user_activity table does not have second_reminder_sent_time column
    activity_rows_second = await db.execute_fetch("SELECT second_reminder_sent FROM user_activity WHERE user_id = ?", (user_id,))
    assert activity_rows_second is not None and len(activity_rows_second) == 1
    activity_second = activity_rows_second[0]
    assert activity_second[0] == 1 # second_reminder_sent is True (1)
    # assert activity_second[1] is not None # No second_reminder_sent_time column

@pytest.mark.asyncio
async def test_is_successful_dialog(db: Database):
    user_with_success = 501
    user_without_success = 502
    user_non_existent = 503
    fixed_timestamp = "2023-01-01T12:00:00+00:00"

    await db.register_user(user_with_success, "user_success", fixed_timestamp)
    await db.register_user(user_without_success, "user_no_success", fixed_timestamp)

    # contact_info is dict, messages is list of dicts
    contact_details = {"email": "success@example.com"}
    dialog_history = [{"role":"user", "message":"This was a great chat."}]
    await db.save_successful_dialog(user_with_success, "user_success_dialog_entry", contact_details, dialog_history)

    assert await db.is_successful_dialog(user_with_success)
    assert not await db.is_successful_dialog(user_without_success)
    assert not await db.is_successful_dialog(user_non_existent)
