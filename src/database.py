import aiosqlite
import os
import json
from string import Template

class Database:
    def __init__(self, db_path: str = "database/dialogs.db"):
        """
        Инициализация базы данных.
        
        Parameters
        ----------
        db_path : str
            Путь к файлу базы данных SQLite
        """
        # Создаем директорию для базы данных, если её нет
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        
    async def init_db(self):
        """
        Инициализация базы данных и создание необходимых таблиц.
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица для хранения всех сообщений диалога
            await db.execute('''
                CREATE TABLE IF NOT EXISTS dialogs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    message TEXT NOT NULL,
                    role TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Таблица для хранения успешно завершенных диалогов с контактной информацией
            await db.execute('''
                CREATE TABLE IF NOT EXISTS successful_dialogs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    contact_info TEXT NOT NULL,
                    messages TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await db.commit()
            
    async def save_message(self, user_id: int, username: str, message: str, role: str):
        """
        Сохранение сообщения в базу данных.
        
        Parameters
        ----------
        user_id : int
            ID пользователя
        username : str
            Имя пользователя
        message : str
            Текст сообщения
        role : str
            Роль отправителя (user/assistant)
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT INTO dialogs (user_id, username, message, role) VALUES (?, ?, ?, ?)',
                (user_id, username, message, role)
            )
            await db.commit()
            
    async def get_dialog(self, user_id: int) -> list:
        """
        Получение всего диалога для пользователя.
        
        Parameters
        ----------
        user_id : int
            ID пользователя
            
        Returns
        -------
        list
            Список сообщений диалога
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT message, role FROM dialogs WHERE user_id = ? ORDER BY timestamp',
                (user_id,)
            ) as cursor:
                messages = await cursor.fetchall()
                return [
                    f"{'User' if role == 'user' else 'ChatGPT'}: {message}"
                    for message, role in messages
                ]
                
    async def save_successful_dialog(self, user_id: int, username: str, contact_info: dict, messages: list) -> int:
        """
        Сохраняет успешный диалог в базу данных.

        Parameters
        ----------
        user_id : int
            ID пользователя
        username : str
            Имя пользователя
        contact_info : dict
            Контактная информация пользователя
        messages : list
            Список сообщений диалога

        Returns
        -------
        int
            ID созданной записи
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                '''
                INSERT INTO successful_dialogs 
                (user_id, username, contact_info, messages)
                VALUES (?, ?, ?, ?)
                ''',
                (user_id, username, json.dumps(contact_info), json.dumps(messages))
            )
            await db.commit()
            return cursor.lastrowid

    async def execute_fetch(self, query: str, params: tuple = None) -> list:
        """
        Выполняет SQL запрос и возвращает результаты.
        
        Parameters
        ----------
        query : str
            SQL запрос
        params : tuple, optional
            Параметры для SQL запроса
            
        Returns
        -------
        list
            Результаты запроса
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, params or ()) as cursor:
                return await cursor.fetchall()

    def format_dialog_html(self, dialog_lines: list, username: str) -> str:
        """
        Форматирование диалога в HTML.
        
        Parameters
        ----------
        dialog_lines : list
            Список строк диалога
        username : str
            Имя пользователя
            
        Returns
        -------
        str
            HTML представление диалога
        """
        html_content = '<!DOCTYPE html>\n<html>\n<head>\n'
        html_content += '<meta charset="UTF-8">\n'
        html_content += Template('<title>Dialog with $username</title>\n').substitute(username=username)
        html_content += '<style>\n'
        html_content += 'body { font-family: Arial, sans-serif; margin: 20px; }\n'
        html_content += '.message { margin: 10px 0; }\n'
        html_content += '.user { color: blue; }\n'
        html_content += '.assistant { color: green; }\n'
        html_content += '</style>\n</head>\n<body>\n'
        
        for line in dialog_lines:
            css_class = 'user' if line.startswith('User:') else 'assistant'
            html_content += Template('<div class="message $css_class">$line</div>\n').substitute(
                css_class=css_class, 
                line=line
            )
        
        html_content += '</body></html>'
        return html_content
