import os
import json
import asyncio
from datetime import datetime
import aiofiles
from typing import Dict

class ContactHandler:
    def __init__(self):
        self.contacts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'client_contacts')
        if not os.path.exists(self.contacts_dir):
            os.makedirs(self.contacts_dir)
        self.file_lock = asyncio.Lock()

    async def save_contact_info(self, username: str, thread_id: str, contact_info: Dict):
        """
        Асинхронно сохраняет контактную информацию клиента в отдельный файл.
        """
        current_date = datetime.now().strftime('%Y-%m-%d')
        filename = f"{username}_{current_date}_{thread_id}.json"
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
