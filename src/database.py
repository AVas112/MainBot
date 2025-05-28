import json
import os
from datetime import datetime, timedelta, timezone # Added timezone
from string import Template

import aiosqlite


class Database:
    def __init__(self, db_path: str = "database/dialogs.db"):
        """
        Database initialization.
        
        Parameters
        ----------
        db_path : str
            Path to the SQLite database file
        """
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        
    async def init_db(self):
        """Initialize the database and create necessary tables."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS dialogs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    message TEXT NOT NULL,
                    role TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS successful_dialogs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    contact_info TEXT NOT NULL,
                    messages TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Создаем таблицу для отслеживания активности пользователей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    user_id INTEGER PRIMARY KEY,
                    last_activity DATETIME NOT NULL,
                    first_reminder_sent BOOLEAN DEFAULT 0,
                    second_reminder_sent BOOLEAN DEFAULT 0
                )
            """)

            await db.commit()
            
    async def save_message(self, user_id: int, username: str, message: str, role: str):
        """
        Saving a message to the database.
        
        Parameters
        ----------
        user_id : int
            User ID
        username : str
            Username
        message : str
            Message text
        role : str
            Sender role (user/assistant)
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO dialogs (user_id, username, message, role) VALUES (?, ?, ?, ?)",
                (user_id, username, message, role)
            )
            await db.commit()
            
            # Обновляем время последней активности пользователя, если сообщение от пользователя
            if role == "user":
                await self.update_user_activity(user_id=user_id)
            
    async def get_dialog(self, user_id: int) -> list:
        """
        Getting the entire dialog for the user.
        
        Parameters
        ----------
        user_id : int
            User ID
            
        Returns
        -------
        list
            List of dialog messages as dictionaries, e.g., [{'role': 'user', 'message': 'Hello'}]
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT role, message FROM dialogs WHERE user_id = ? ORDER BY timestamp",
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [{"role": row[0], "message": row[1]} for row in rows]
                
    async def save_successful_dialog(self, user_id: int, username: str, contact_info: dict, messages: list) -> int:
        """
        Saves a successful dialog to the database.

        Parameters
        ----------
        user_id : int
            User ID
        username : str
            Username
        contact_info : dict
            User contact information
        messages : list
            List of dialog messages

        Returns
        -------
        int
            ID of the created record
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO successful_dialogs 
                (user_id, username, contact_info, messages)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, username, json.dumps(contact_info), json.dumps(messages))
            )
            await db.commit()
            return cursor.lastrowid

    async def execute_fetch(self, query: str, params: tuple = None) -> list:
        """
        Executes an SQL query and returns the results.
        
        Parameters
        ----------
        query : str
            SQL query
        params : tuple, optional
            Parameters for the SQL query
            
        Returns
        -------
        list
            Query results
        """
        async with (
            aiosqlite.connect(self.db_path) as db,
            db.execute(query, params or ()) as cursor
        ):
            return await cursor.fetchall()

    async def execute_commit(self, query: str, params: tuple = None) -> None:
        """
        Executes an SQL query that modifies data and commits the changes.
        
        Parameters
        ----------
        query : str
            SQL query
        params : tuple, optional
            Parameters for the SQL query
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, params or ())
            await db.commit()

    def format_dialog_html(self, dialog_lines: list, username: str) -> str:
        """
        Formatting the dialog into HTML.
        
        Parameters
        ----------
        dialog_lines : list
            List of dialog lines
        username : str
            Username
            
        Returns
        -------
        str
            HTML representation of the dialog
        """
        html_content = "<!DOCTYPE html>\n<html>\n<head>\n"
        html_content += '<meta charset="UTF-8">\n'
        html_content += Template("<title>Dialog with $username</title>\n").substitute(username=username)
        html_content += "<style>\n"
        html_content += "body { font-family: Arial, sans-serif; margin: 20px; }\n"
        html_content += ".message { margin: 10px 0; padding: 5px; border-bottom: 1px solid #eee; }\n"
        html_content += ".user-message { color: blue; text-align: left; }\n"
        html_content += ".assistant-message { color: green; text-align: left; }\n"
        html_content += ".system-message { color: grey; font-style: italic; text-align: center; }\n"
        html_content += "</style>\n</head>\n<body>\n"
        html_content += f"<h2>Dialog with {username}</h2>\n"

        if not dialog_lines:
            html_content += "<p>No messages in this dialog yet.</p>\n"
        else:
            for entry in dialog_lines:
                role = entry.get('role', 'unknown').lower()
                message_text = entry.get('message', '')
                css_class = f"{role}-message" # e.g., user-message, assistant-message
                
                # Sanitize message_text before putting it into HTML
                import html
                escaped_message = html.escape(message_text)

                html_content += Template('<div class="message $css_class"><strong>$Role:</strong> $message</div>\n').substitute(
                    css_class=css_class,
                    Role=role.capitalize(),
                    message=escaped_message
                )
        
        html_content += "</body>\n</html>"
        return html_content

    async def is_user_registered(self, user_id: int) -> bool:
        """Проверяет, существует ли пользователь в таблице dialogs."""
        result = await self.execute_fetch(
            "SELECT 1 FROM dialogs WHERE user_id = ? LIMIT 1", (user_id,)
        )
        return bool(result)

    async def register_user(self, user_id: int, username: str, first_seen: str) -> None:
        """Регистрирует нового пользователя в таблице dialogs."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO dialogs (user_id, username, message, role, timestamp) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, "User registered.", "system", first_seen) # Store a system message for registration
            )
            await db.commit()
            # Also ensure an entry in user_activity, as registration implies activity
            await self.update_user_activity(user_id)

    async def update_user_activity(self, user_id: int) -> None:
        """
        Updates the last activity time for a user and resets reminder flags.
        If the user does not exist in user_activity, a new record is created.
        
        Parameters
        ----------
        user_id : int
            User ID
        """
        # Use ISO 8601 format for datetime strings, consistent with SQLite best practices
        current_time_iso = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO user_activity (user_id, last_activity, first_reminder_sent, second_reminder_sent)
                VALUES (?, ?, 0, 0)
                ON CONFLICT(user_id) DO UPDATE SET
                    last_activity = excluded.last_activity,
                    first_reminder_sent = 0,
                    second_reminder_sent = 0;
                """,
                (user_id, current_time_iso)
            )
            await db.commit()

    async def get_users_for_first_reminder(self, minutes: int) -> list:
        """
        Получает список пользователей для отправки первого напоминания.
        
        Parameters
        ----------
        minutes : int
            Minimum inactivity duration in minutes for the first reminder.
            
        Returns
        -------
        list
            List of user IDs eligible for the first reminder.
        """
        time_threshold_iso = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        query = """
            SELECT ua.user_id
            FROM user_activity ua
            LEFT JOIN successful_dialogs sd ON ua.user_id = sd.user_id
            WHERE ua.last_activity < ?
              AND ua.first_reminder_sent = 0
              AND sd.user_id IS NULL; 
        """
        # sd.user_id IS NULL ensures we don't remind users with successful dialogs.
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, (time_threshold_iso,)) as cursor:
                users = await cursor.fetchall()
                return [user[0] for user in users]

    async def get_users_for_second_reminder(self, minutes: int) -> list:
        """
        Получает список пользователей для отправки второго напоминания.
        
        Parameters
        ----------
        minutes : int
            Minimum inactivity duration in minutes after the first reminder for the second reminder.
            
        Returns
        -------
        list
            List of user IDs eligible for the second reminder.
        """
        # This implies that last_activity is older than 'minutes' AND a first reminder was sent
        # and that first reminder was sent more than 'minutes' ago.
        # The exact logic for "time since first reminder" needs a 'first_reminder_sent_time' column.
        # Assuming current schema: last_activity < threshold AND first_reminder_sent = 1
        # If 'first_reminder_sent_time' is added, the query would be more precise.
        # For now, this selects users whose last activity is older than `minutes` and have received first reminder.
        # This might not be what's intended if `minutes` refers to time *after* first reminder.
        # Let's assume 'minutes' is overall inactivity like in get_users_for_first_reminder for now.
        
        time_threshold_iso = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        query = """
            SELECT ua.user_id
            FROM user_activity ua
            LEFT JOIN successful_dialogs sd ON ua.user_id = sd.user_id
            WHERE ua.last_activity < ?       -- User has been inactive for at least 'minutes'
              AND ua.first_reminder_sent = 1 -- First reminder has been sent
              AND ua.second_reminder_sent = 0 -- Second reminder has not been sent
              AND sd.user_id IS NULL;        -- No successful dialog with this user
        """
        # If you add `first_reminder_sent_time` to user_activity:
        # query = """
        #     SELECT ua.user_id
        #     FROM user_activity ua
        #     LEFT JOIN successful_dialogs sd ON ua.user_id = sd.user_id
        #     WHERE ua.first_reminder_sent_time < ? -- First reminder sent more than 'minutes' ago
        #       AND ua.first_reminder_sent = 1
        #       AND ua.second_reminder_sent = 0
        #       AND sd.user_id IS NULL;
        # """
        # time_threshold_for_second_reminder_iso = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, (time_threshold_iso,)) as cursor:
                users = await cursor.fetchall()
                return [user[0] for user in users]

    async def mark_first_reminder_sent(self, user_id: int) -> None:
        """
        Marks that the first reminder has been sent to the user and records the time.
        
        Parameters
        ----------
        user_id : int
            User ID
        """
        # Add/update 'first_reminder_sent_time' if you add this column
        # current_time_iso = datetime.now(timezone.utc).isoformat()
        # await db.execute(
        #    "UPDATE user_activity SET first_reminder_sent = 1, first_reminder_sent_time = ? WHERE user_id = ?",
        #    (current_time_iso, user_id,)
        # )
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE user_activity SET first_reminder_sent = 1 WHERE user_id = ?", (user_id,)
            )
            await db.commit()

    async def mark_second_reminder_sent(self, user_id: int) -> None:
        """
        Marks that the second reminder has been sent to the user and records the time.
        
        Parameters
        ----------
        user_id : int
            User ID
        """
        # Add/update 'second_reminder_sent_time' if you add this column
        # current_time_iso = datetime.now(timezone.utc).isoformat()
        # await db.execute(
        #     "UPDATE user_activity SET second_reminder_sent = 1, second_reminder_sent_time = ? WHERE user_id = ?",
        #     (current_time_iso, user_id,)
        # )
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE user_activity SET second_reminder_sent = 1 WHERE user_id = ?", (user_id,)
            )
            await db.commit()

    async def is_successful_dialog(self, user_id: int) -> bool:
        """
        Проверяет, был ли диалог с пользователем отмечен как успешный.
        
        Parameters
        ----------
        user_id : int
            ID пользователя
            
        Returns
        -------
        bool
            True, если диалог был успешным, иначе False
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM successful_dialogs WHERE user_id = ? LIMIT 1",
                (user_id,)
            )
            result = await cursor.fetchone()
            return bool(result)
