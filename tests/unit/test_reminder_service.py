import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.reminder_service import ReminderService
# Removed: from src.models import User, Message

# Fixtures for mocks

@pytest.fixture
def mock_config_reminder_enabled(mocker):
    mock_cfg = MagicMock()
    mock_cfg.REMINDER.ENABLED = True
    mock_cfg.REMINDER.FIRST_REMINDER_TIME = 30
    mock_cfg.REMINDER.SECOND_REMINDER_TIME = 60
    mock_cfg.REMINDER.FIRST_REMINDER_PROMPT = "First reminder: {minutes} min"
    mock_cfg.REMINDER.SECOND_REMINDER_PROMPT = "Second reminder: {minutes} min"
    mock_cfg.REMINDER.CHECK_INTERVAL = 60
    mocker.patch('src.reminder_service.CONFIG', mock_cfg)
    return mock_cfg

@pytest.fixture
def mock_config_reminder_disabled(mocker):
    mock_cfg = MagicMock()
    mock_cfg.REMINDER.ENABLED = False
    mock_cfg.REMINDER.CHECK_INTERVAL = 60 # Added for check_interval
    mocker.patch('src.reminder_service.CONFIG', mock_cfg)
    return mock_cfg

@pytest.fixture
def mock_telegram_bot_instance(mocker):
    bot = AsyncMock()
    bot.bot = AsyncMock()
    bot.threads = {"123": "thread_abc"} # Store chat_id as string key
    bot.usernames = {123: "testuser"} # Store user_id as int key, as used in reminder_service
    bot.send_message = AsyncMock()
    return bot

@pytest.fixture
def mock_db_instance():
    db = AsyncMock()
    db.get_users_for_first_reminder.return_value = []
    db.get_users_for_second_reminder.return_value = []
    db.is_successful_dialog.return_value = False
    db.save_message = AsyncMock()
    db.mark_first_reminder_sent = AsyncMock()
    db.mark_second_reminder_sent = AsyncMock()
    return db

@pytest.fixture
def mock_chatgpt_assistant_instance():
    assistant = AsyncMock()
    assistant.get_response.return_value = "Test reminder message"
    return assistant

@pytest.fixture
async def reminder_service(mock_telegram_bot_instance, mock_db_instance, mock_chatgpt_assistant_instance, mock_config_reminder_enabled):
    service = ReminderService(
        telegram_bot=mock_telegram_bot_instance,
        db=mock_db_instance,
        chatgpt_assistant=mock_chatgpt_assistant_instance
    )
    yield service
    if service.is_running:
        await service.stop()

@pytest.fixture
async def reminder_service_disabled_config(mock_telegram_bot_instance, mock_db_instance, mock_chatgpt_assistant_instance, mock_config_reminder_disabled):
    # Use the disabled config fixture
    service = ReminderService(
        telegram_bot=mock_telegram_bot_instance,
        db=mock_db_instance,
        chatgpt_assistant=mock_chatgpt_assistant_instance
    )
    yield service
    if service.is_running:
        await service.stop()


# Tests

@pytest.mark.asyncio
async def test_reminder_service_initialization(reminder_service, mock_telegram_bot_instance, mock_db_instance, mock_chatgpt_assistant_instance, mock_config_reminder_enabled):
    assert reminder_service.telegram_bot == mock_telegram_bot_instance
    assert reminder_service.db == mock_db_instance
    assert reminder_service.chatgpt_assistant == mock_chatgpt_assistant_instance
    assert not reminder_service.is_running
    assert reminder_service.check_interval == mock_config_reminder_enabled.REMINDER.CHECK_INTERVAL

@pytest.mark.asyncio
async def test_reminder_service_start_stop(reminder_service, mock_config_reminder_enabled): # Added mock_config_reminder_enabled
    assert not reminder_service.is_running
    await reminder_service.start()
    assert reminder_service.is_running
    assert reminder_service.task is not None # Changed from _check_inactive_task
    await reminder_service.stop()
    assert not reminder_service.is_running
    assert reminder_service.task is None # Changed from _check_inactive_task

@pytest.mark.asyncio
async def test_reminder_service_does_not_start_if_disabled(reminder_service_disabled_config):
    await reminder_service_disabled_config.start()
    assert not reminder_service_disabled_config.is_running
    assert reminder_service_disabled_config.task is None # Changed from _check_inactive_task

@pytest.mark.asyncio
async def test_send_first_reminder(reminder_service, mock_db_instance, mock_telegram_bot_instance, mock_chatgpt_assistant_instance, mock_config_reminder_enabled):
    user_id = 123 # Use user_id directly
    # Ensure thread_id corresponds to this user_id (as string key)
    mock_telegram_bot_instance.threads = {str(user_id): "thread_abc"}
    mock_telegram_bot_instance.usernames = {user_id: "testuser"}


    mock_db_instance.get_users_for_first_reminder.return_value = [user_id]

    await reminder_service._check_and_send_reminders() # Call the public orchestrator

    mock_db_instance.get_users_for_first_reminder.assert_called_once_with(minutes=mock_config_reminder_enabled.REMINDER.FIRST_REMINDER_TIME)
    mock_db_instance.is_successful_dialog.assert_called_once_with(user_id=user_id)
    mock_chatgpt_assistant_instance.get_response.assert_called_once_with(
        user_message=mock_config_reminder_enabled.REMINDER.FIRST_REMINDER_PROMPT.format(minutes=mock_config_reminder_enabled.REMINDER.FIRST_REMINDER_TIME),
        thread_id="thread_abc", # Correct thread_id for this user
        user_id=str(user_id) # user_id passed as string
    )
    mock_telegram_bot_instance.bot.send_message.assert_called_once_with(chat_id=user_id, text="Test reminder message", parse_mode="HTML")
    mock_db_instance.save_message.assert_called_once_with(
        user_id=user_id,
        username="testuser",
        message="Test reminder message",
        role="assistant"
    )
    mock_db_instance.mark_first_reminder_sent.assert_called_once_with(user_id=user_id)

@pytest.mark.asyncio
async def test_send_second_reminder(reminder_service, mock_db_instance, mock_telegram_bot_instance, mock_chatgpt_assistant_instance, mock_config_reminder_enabled):
    user_id = 456 # Use a different user_id for clarity
    mock_telegram_bot_instance.threads = {str(user_id): "thread_def"}
    mock_telegram_bot_instance.usernames = {user_id: "anotheruser"}

    mock_db_instance.get_users_for_second_reminder.return_value = [user_id]
    # Ensure first reminder users don't interfere
    mock_db_instance.get_users_for_first_reminder.return_value = []


    await reminder_service._check_and_send_reminders() # Call the public orchestrator

    mock_db_instance.get_users_for_second_reminder.assert_called_once_with(minutes=mock_config_reminder_enabled.REMINDER.SECOND_REMINDER_TIME)
    mock_db_instance.is_successful_dialog.assert_called_once_with(user_id=user_id)
    mock_chatgpt_assistant_instance.get_response.assert_called_once_with(
        user_message=mock_config_reminder_enabled.REMINDER.SECOND_REMINDER_PROMPT.format(minutes=mock_config_reminder_enabled.REMINDER.SECOND_REMINDER_TIME),
        thread_id="thread_def",
        user_id=str(user_id)
    )
    mock_telegram_bot_instance.bot.send_message.assert_called_once_with(chat_id=user_id, text="Test reminder message", parse_mode="HTML")
    mock_db_instance.save_message.assert_called_once_with(
        user_id=user_id,
        username="anotheruser",
        message="Test reminder message",
        role="assistant"
    )
    mock_db_instance.mark_second_reminder_sent.assert_called_once_with(user_id=user_id)

@pytest.mark.asyncio
async def test_send_first_reminder_skip_successful_dialog(reminder_service, mock_db_instance, mock_config_reminder_enabled):
    user_id = 123
    mock_db_instance.get_users_for_first_reminder.return_value = [user_id]
    mock_db_instance.is_successful_dialog.return_value = True

    await reminder_service._check_and_send_reminders()

    mock_db_instance.is_successful_dialog.assert_called_once_with(user_id=user_id)
    reminder_service.chatgpt_assistant.get_response.assert_not_called()
    reminder_service.telegram_bot.bot.send_message.assert_not_called() # Check bot.send_message
    reminder_service.db.mark_first_reminder_sent.assert_not_called()


@pytest.mark.asyncio
async def test_send_second_reminder_skip_successful_dialog(reminder_service, mock_db_instance, mock_config_reminder_enabled):
    user_id = 456
    mock_db_instance.get_users_for_second_reminder.return_value = [user_id]
    mock_db_instance.is_successful_dialog.return_value = True
    mock_db_instance.get_users_for_first_reminder.return_value = []


    await reminder_service._check_and_send_reminders()

    mock_db_instance.is_successful_dialog.assert_called_once_with(user_id=user_id)
    reminder_service.chatgpt_assistant.get_response.assert_not_called()
    reminder_service.telegram_bot.bot.send_message.assert_not_called() # Check bot.send_message
    reminder_service.db.mark_second_reminder_sent.assert_not_called()


@pytest.mark.asyncio
async def test_send_reminder_no_thread_id(reminder_service, mock_db_instance, mock_telegram_bot_instance, caplog, mock_config_reminder_enabled):
    user_id_no_thread = 789
    # This user_id will not be in mock_telegram_bot_instance.threads
    mock_db_instance.get_users_for_first_reminder.return_value = [user_id_no_thread]
    mock_db_instance.get_users_for_second_reminder.return_value = []


    await reminder_service._check_and_send_reminders()

    # is_successful_dialog IS called before checking thread_id
    mock_db_instance.is_successful_dialog.assert_called_once_with(user_id=user_id_no_thread)
    assert f"Не найден thread_id для пользователя {user_id_no_thread}" in caplog.text
    mock_telegram_bot_instance.bot.send_message.assert_not_called() # Check bot.send_message


@pytest.mark.asyncio
async def test_check_inactive_users_loop_exception_handling(reminder_service, mock_db_instance, caplog):
    mock_db_instance.get_users_for_first_reminder.side_effect = Exception("DB error")

    # To test the loop, we need to let it run once and then stop it.
    # We can't directly call the loop method as it's intended to run in a task.
    # Instead, we start the service, wait a bit for the loop to execute (and hit the exception), then stop.
    # We also need to ensure CONFIG.REMINDER.ENABLED is True for the loop to run.
    with patch('src.reminder_service.CONFIG.REMINDER.ENABLED', True):
        await reminder_service.start()
        await asyncio.sleep(0.1) # Give some time for the loop to run once
        await reminder_service.stop()

    assert reminder_service.is_running is False # Ensure it stopped
    # The logger message in _check_inactive_users_loop is "Ошибка при проверке неактивных пользователей: {e}"
    assert "Ошибка при проверке неактивных пользователей: DB error" in caplog.text


@pytest.mark.asyncio
async def test_send_first_reminder_no_users(reminder_service, mock_db_instance, mock_config_reminder_enabled):
    mock_db_instance.get_users_for_first_reminder.return_value = []
    mock_db_instance.get_users_for_second_reminder.return_value = [] # Ensure no interference

    await reminder_service._check_and_send_reminders()

    mock_db_instance.get_users_for_first_reminder.assert_called_once_with(minutes=mock_config_reminder_enabled.REMINDER.FIRST_REMINDER_TIME)
    reminder_service.chatgpt_assistant.get_response.assert_not_called()
    reminder_service.telegram_bot.bot.send_message.assert_not_called() # Check bot.send_message

@pytest.mark.asyncio
async def test_send_second_reminder_no_users(reminder_service, mock_db_instance, mock_config_reminder_enabled):
    mock_db_instance.get_users_for_first_reminder.return_value = [] # Ensure no interference
    mock_db_instance.get_users_for_second_reminder.return_value = []

    await reminder_service._check_and_send_reminders()

    mock_db_instance.get_users_for_second_reminder.assert_called_once_with(minutes=mock_config_reminder_enabled.REMINDER.SECOND_REMINDER_TIME)
    reminder_service.chatgpt_assistant.get_response.assert_not_called()
    reminder_service.telegram_bot.bot.send_message.assert_not_called() # Check bot.send_message

@pytest.mark.asyncio
async def test_send_reminder_chatgpt_error(reminder_service, mock_db_instance, mock_chatgpt_assistant_instance, caplog, mock_config_reminder_enabled, mock_telegram_bot_instance):
    user_id = 123
    mock_telegram_bot_instance.threads = {str(user_id): "thread_abc"}
    mock_db_instance.get_users_for_first_reminder.return_value = [user_id]
    mock_db_instance.get_users_for_second_reminder.return_value = []
    mock_chatgpt_assistant_instance.get_response.side_effect = Exception("ChatGPT API error")

    await reminder_service._check_and_send_reminders()
    
    # The log message in _send_reminder is "Ошибка при отправке напоминания пользователю {user_id}: {e}"
    assert f"Ошибка при отправке напоминания пользователю {user_id}: ChatGPT API error" in caplog.text
    reminder_service.telegram_bot.bot.send_message.assert_not_called()
    # mark_first_reminder_sent is called *after* _send_reminder in _check_and_send_reminders
    # If _send_reminder fails, mark_first_reminder_sent for that user should not be called.
    # However, if there were other users, it might be called for them.
    # For this specific user, it should not be called.
    # Let's check if it was called with user_id. If it was, it's an issue.
    # A more precise check might be needed if there were multiple users.
    # If the list is empty, the loop won't run, and the assertion passes.
    # If it's not empty, it means the method was called, and we check the user_id.
    # A simpler way is to assert it wasn't called with this specific user_id or at all if only one user is processed.
    mock_db_instance.mark_first_reminder_sent.assert_not_called()


@pytest.mark.asyncio
async def test_send_reminder_telegram_error(reminder_service, mock_db_instance, mock_telegram_bot_instance, mock_chatgpt_assistant_instance, caplog, mock_config_reminder_enabled):
    user_id = 123
    mock_telegram_bot_instance.threads = {str(user_id): "thread_abc"}
    mock_telegram_bot_instance.usernames = {user_id: "testuser"}
    mock_db_instance.get_users_for_first_reminder.return_value = [user_id]
    mock_db_instance.get_users_for_second_reminder.return_value = []
    # Ensure get_response returns normally
    mock_chatgpt_assistant_instance.get_response.return_value = "Test reminder message"
    mock_telegram_bot_instance.bot.send_message.side_effect = Exception("Telegram API error")

    await reminder_service._check_and_send_reminders()

    assert f"Ошибка при отправке напоминания пользователю {user_id}: Telegram API error" in caplog.text
    # save_message is called after send_message in _send_reminder. If send_message fails, save_message should not be called.
    mock_db_instance.save_message.assert_not_called()
    # Similar to above, mark_first_reminder_sent should not be called for this user.
    mock_db_instance.mark_first_reminder_sent.assert_not_called()


@pytest.mark.asyncio
async def test_send_reminder_save_message_error(reminder_service, mock_db_instance, mock_telegram_bot_instance, mock_chatgpt_assistant_instance, caplog, mock_config_reminder_enabled):
    user_id = 123
    mock_telegram_bot_instance.threads = {str(user_id): "thread_abc"}
    mock_telegram_bot_instance.usernames = {user_id: "testuser"} # Ensure username is found
    mock_db_instance.get_users_for_first_reminder.return_value = [user_id]
    mock_db_instance.get_users_for_second_reminder.return_value = []
    mock_chatgpt_assistant_instance.get_response.return_value = "Test reminder message"
    mock_db_instance.save_message.side_effect = Exception("DB save_message error")

    await reminder_service._check_and_send_reminders()

    # Message sending should still happen
    mock_telegram_bot_instance.bot.send_message.assert_called_once()
    assert f"Ошибка при отправке напоминания пользователю {user_id}: DB save_message error" in caplog.text
    # Since _send_reminder will return False due to the save_message error,
    # mark_first_reminder_sent should NOT be called by _check_and_send_reminders.
    mock_db_instance.mark_first_reminder_sent.assert_not_called()


@pytest.mark.asyncio
async def test_send_reminder_mark_sent_error(reminder_service, mock_db_instance, mock_telegram_bot_instance, mock_chatgpt_assistant_instance, caplog, mock_config_reminder_enabled):
    user_id = 123
    mock_telegram_bot_instance.threads = {str(user_id): "thread_abc"}
    mock_telegram_bot_instance.usernames = {user_id: "testuser"}
    mock_db_instance.get_users_for_first_reminder.return_value = [user_id]
    mock_db_instance.get_users_for_second_reminder.return_value = []
    mock_chatgpt_assistant_instance.get_response.return_value = "Test reminder message"
    mock_db_instance.mark_first_reminder_sent.side_effect = Exception("DB mark_first_reminder_sent error")

    with pytest.raises(Exception, match="DB mark_first_reminder_sent error"):
        await reminder_service._check_and_send_reminders()

    # Message sending and saving should still happen because they occur before the error
    mock_telegram_bot_instance.bot.send_message.assert_called_once()
    mock_db_instance.save_message.assert_called_once()
    # Verify that no error was logged by _send_reminder itself for this user,
    # as the error happens *after* _send_reminder has successfully completed.
    # The specific log for this error would be handled by the caller of _check_and_send_reminders.
    for record in caplog.records:
        if record.levelname == "ERROR" and f"Ошибка при отправке напоминания пользователю {user_id}" in record.message:
            assert False, f"_send_reminder logged an error for user {user_id} which was not expected here."
    # If we wanted to check the log from _check_inactive_users_loop, this test would need to be structured differently.
    # For this unit test of _check_and_send_reminders, we just confirm it propagates the error.

@pytest.mark.asyncio
@patch('asyncio.sleep', new_callable=AsyncMock) # Mock asyncio.sleep
async def test_check_inactive_users_loop_runs_and_calls_reminders(mock_sleep, reminder_service, mock_db_instance):
    # This test is a bit more complex as it tests the loop itself.
    # We'll make the loop run a few times and check if the reminder methods are called.

    # Let's simulate that the loop runs twice then an external event stops it.
    # We use a side effect on sleep to stop the loop after a couple of iterations.
    stop_event = asyncio.Event()
    call_count = 0
    async def sleep_side_effect(duration):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            stop_event.set() # Signal to stop the service externally
            # To prevent the reminder_service.stop() from waiting indefinitely if the task
            # is stuck in sleep, we raise CancelledError here.
            # This simulates the task being cancelled.
            raise asyncio.CancelledError
        await asyncio.sleep(0) # Actual sleep for a very short duration

    mock_sleep.side_effect = sleep_side_effect

    # Mock the actual reminder sending method
    # This needs to be mocked *before* start() is called so the task uses the mock
    reminder_service._send_reminder = AsyncMock(name="_send_reminder", return_value=True) # Ensure it returns True to allow marking as sent

    # Ensure CONFIG.REMINDER.ENABLED is True for this test path
    # The reminder_service fixture already uses mock_config_reminder_enabled.

    # Setup mock DB calls for inside the loop
    # Ensure that get_users_for_first_reminder returns a user so that _send_first_reminder is called.
    mock_db_instance.get_users_for_first_reminder.return_value = [123] # Example user_id
    mock_db_instance.get_users_for_second_reminder.return_value = [] # No second reminders for simplicity here
    # is_successful_dialog should return False for the reminder to be sent
    mock_db_instance.is_successful_dialog.return_value = False
    # Ensure thread_id exists for user 123
    reminder_service.telegram_bot.threads = {"123": "thread_for_loop_test"}


    await reminder_service.start() # Start the service, which starts the loop

    try:
        # Wait for the stop_event or a timeout
        await asyncio.wait_for(stop_event.wait(), timeout=1.0)
    except asyncio.TimeoutError:
        # This might happen if the sleep_side_effect logic is not perfect
        # or if the loop takes too long.
        pass
    finally:
        # Ensure service is stopped, even if timeout occurred
        if reminder_service.is_running:
            await reminder_service.stop()


    # Assertions
    assert call_count >= 1 # Ensure sleep was called, meaning the loop ran
    # Check if reminder methods were called.
    # Depending on timing and the 0-second sleep, they might be called multiple times or once.
    # At least once is a good check.
    # We check if _send_reminder was called, as it's the actual worker method.
    reminder_service._send_reminder.assert_called()
    # Ensure sleep was called with the configured interval
    mock_sleep.assert_any_call(reminder_service.check_interval)

    # Also check that mark_first_reminder_sent was called, implying _send_reminder returned True
    mock_db_instance.mark_first_reminder_sent.assert_called_with(user_id=123) # From the [123] returned by get_users_for_first_reminder

    # Reset the mock_sleep to avoid interference with other tests
    mock_sleep.side_effect = None
