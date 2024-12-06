from datetime import datetime
import json
import os

import aiofiles
from string import Template
from typing import Dict
import asyncio

class ContactHandler:
    def __init__(self):
        self.contacts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'client_contacts')
        if not os.path.exists(self.contacts_dir):
            os.makedirs(self.contacts_dir)
        self.file_lock = asyncio.Lock()

    async def store_contact_info(self, username: str, thread_id: str, contact_info: Dict):
        """Сохраняет контактную информацию клиента в отдельный файл.

        Parameters
        ----------
        username : str
            Имя пользователя клиента
        thread_id : str
            Идентификатор диалога
        contact_info : Dict
            Словарь с контактной информацией

        Returns
        -------
        str
            Путь к сохраненному файлу
        """
        current_date = datetime.now().strftime('%Y-%m-%d')
        filename_template = Template("${username}_${current_date}_${thread_id}.json")
        filename = filename_template.substitute(
            username=username,
            current_date=current_date,
            thread_id=thread_id
        )
        filepath = os.path.join(self.contacts_dir, filename)

        contact_data = {
            "timestamp": datetime.now().isoformat(),
            "thread_id": thread_id,
            "username": username,
            "contact_info": contact_info
        }

        async with self.file_lock:
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(contact_data, ensure_ascii=False, indent=2))

        return filepath
