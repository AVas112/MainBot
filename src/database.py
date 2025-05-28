import json
import os
from datetime import datetime, timedelta
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
            List of dialog messages
        """
        async with (
            aiosqlite.connect(self.db_path) as db,
            db.execute(
                "SELECT message, role FROM dialogs WHERE user_id = ? ORDER BY timestamp",
                (user_id,)
            ) as cursor
        ):
            messages = await cursor.fetchall()
            return [
                f"{'User' if role == 'user' else 'ChatGPT'}: {message}"
                    for message, role in messages
                ]
                
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
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params or ())
            
            # Проверяем, является ли запрос модифицирующим (INSERT, UPDATE, DELETE)
            query_upper = query.upper().strip()
            is_modifying = query_upper.startswith(('INSERT', 'UPDATE', 'DELETE'))
            
            if is_modifying:
                await db.commit()
                return []  # Для модифицирующих запросов возвращаем пустой список
            else:
                return await cursor.fetchall()

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
        html_content += ".message { margin: 10px 0; }\n"
        html_content += ".user { color: blue; }\n"
        html_content += ".assistant { color: green; }\n"
        html_content += "</style>\n</head>\n<body>\n"
        
        for line in dialog_lines:
            css_class = "user" if line.startswith("User:") else "assistant"
            html_content += Template('<div class="message $css_class">$line</div>\n').substitute(
                css_class=css_class, 
                line=line
            )
        
        html_content += "</body></html>"
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
                "INSERT INTO dialogs (user_id, username, message, role, timestamp) VALUES (?, ?, ?, ?, ?)" ,
                (user_id, username, "", "system", first_seen)
            )
            await db.commit()
            
    async def update_user_activity(self, user_id: int) -> None:
        """
        Обновляет время последней активности пользователя и сбрасывает статусы отправки напоминаний.
        
        Parameters
        ----------
        user_id : int
            ID пользователя
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, существует ли запись для пользователя
            cursor = await db.execute(
                "SELECT 1 FROM user_activity WHERE user_id = ?",
                (user_id,)
            )
            exists = await cursor.fetchone()
            
            if exists:
                # Обновляем существующую запись
                await db.execute(
                    """UPDATE user_activity 
                       SET last_activity = ?, 
                           first_reminder_sent = 0, 
                           second_reminder_sent = 0 
                       WHERE user_id = ?""",
                    (current_time, user_id)
                )
            else:
                # Создаем новую запись
                await db.execute(
                    "INSERT INTO user_activity (user_id, last_activity) VALUES (?, ?)",
                    (user_id, current_time)
                )
            await db.commit()
    
    async def get_users_for_first_reminder(self, minutes: int) -> list:
        """
        Получает список пользователей для отправки первого напоминания.
        
        Parameters
        ----------
        minutes : int
            Время неактивности в минутах для первого напоминания
            
        Returns
        -------
        list
            Список ID пользователей
        """
        time_threshold = (datetime.now() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT user_id FROM user_activity 
                   WHERE last_activity < ? 
                   AND first_reminder_sent = 0""",
                (time_threshold,)
            )
            users = await cursor.fetchall()
            return [user[0] for user in users] if users else []
    
    async def get_users_for_second_reminder(self, minutes: int) -> list:
        """
        Получает список пользователей для отправки второго напоминания.
        
        Parameters
        ----------
        minutes : int
            Время неактивности в минутах для второго напоминания
            
        Returns
        -------
        list
            Список ID пользователей
        """
        time_threshold = (datetime.now() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT user_id FROM user_activity 
                   WHERE last_activity < ? 
                   AND first_reminder_sent = 1 
                   AND second_reminder_sent = 0""",
                (time_threshold,)
            )
            users = await cursor.fetchall()
            return [user[0] for user in users]
    
    async def mark_first_reminder_sent(self, user_id: int) -> None:
        """
        Отмечает, что первое напоминание было отправлено пользователю.
        
        Parameters
        ----------
        user_id : int
            ID пользователя
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Проверим, существует ли запись для этого пользователя
            cursor = await db.execute(
                "SELECT 1 FROM user_activity WHERE user_id = ?",
                (user_id,)
            )
            exists = await cursor.fetchone()
            
            if not exists:
                # Если записи нет, создадим ее
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await db.execute(
                    "INSERT INTO user_activity (user_id, last_activity, first_reminder_sent, second_reminder_sent) VALUES (?, ?, 1, 0)",
                    (user_id, current_time)
                )
            else:
                # Иначе обновим существующую
                await db.execute(
                    "UPDATE user_activity SET first_reminder_sent = 1 WHERE user_id = ?",
                    (user_id,)
                )
            await db.commit()
    
    async def mark_second_reminder_sent(self, user_id: int) -> None:
        """
        Отмечает, что второе напоминание было отправлено пользователю.
        
        Parameters
        ----------
        user_id : int
            ID пользователя
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Проверим, существует ли запись для этого пользователя
            cursor = await db.execute(
                "SELECT 1 FROM user_activity WHERE user_id = ?",
                (user_id,)
            )
            exists = await cursor.fetchone()
            
            if not exists:
                # Если записи нет, создадим ее
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                await db.execute(
                    "INSERT INTO user_activity (user_id, last_activity, first_reminder_sent, second_reminder_sent) VALUES (?, ?, 1, 1)",
                    (user_id, current_time)
                )
            else:
                # Иначе обновим существующую
                await db.execute(
                    "UPDATE user_activity SET second_reminder_sent = 1 WHERE user_id = ?",
                    (user_id,)
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
