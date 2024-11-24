import os
import logging
import smtplib
import json
import aiofiles
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from datetime import datetime
from bot.chatgpt_assistant import ChatGPTAssistant

class TelegramBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.application = Application.builder().token(self.token).build()
        self.logger = logging.getLogger(__name__)
        self.dialogs = {}  # Будет хранить список сообщений для каждого пользователя
        self.threads = self.load_threads()
        self.file_lock = asyncio.Lock()

        # Email configuration
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.notification_email = os.getenv('NOTIFICATION_EMAIL')

        # Установка директорий для диалогов и ответов
        self.dialogs_dir = 'dialogs'
        self.responses_dir = 'responses'
        self.emails_dir = 'emails'  # Новая директория для email сообщений
        
        # Создаем директории, если они не существуют
        for directory in [self.dialogs_dir, self.responses_dir, self.emails_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)

        # Создаем ChatGPTAssistant после инициализации всех необходимых атрибутов
        self.chatgpt_assistant = ChatGPTAssistant(telegram_bot=self)

    def get_unique_filename(self, directory, user_id, username, base_filename):
        """
        Генерирует уникальное имя файла в заданном каталоге,
        добавляя числовой суффикс к основному имени файла, если файл уже существует.
        """
        if not os.path.exists(directory):
            os.makedirs(directory)

        count = 1
        filename = f"{user_id}_{username}_{base_filename}"
        while os.path.exists(os.path.join(directory, filename)):
            filename = f"{user_id}_{username}_{base_filename}_{count}"
            count += 1
        return filename

    def run(self):
        self.logger.info("Setting up Telegram bot...")
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.logger.info("Starting Telegram bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    async def start(self, update: Update, context):
        self.logger.info(f"User {update.effective_user.id} started the bot")
        await update.message.reply_text('Привет. Я консультант компании КлинингУМамы. Чем я могу вам помочь?')

    async def help(self, update: Update, context):
        self.logger.info(f"User {update.effective_user.id} requested help")
        help_text = (
            "Here are the available commands:\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
        )
        await update.message.reply_text(help_text)

    async def handle_message(self, update: Update, context):
        """Обработка входящих сообщений"""
        user_id = update.effective_user.id
        username = update.effective_user.username or str(user_id)
        message_text = update.message.text

        # Инициализируем список диалога для пользователя, если его нет
        if user_id not in self.dialogs:
            self.dialogs[user_id] = []
        
        # Добавляем сообщение пользователя в диалог
        self.dialogs[user_id].append(f"User: {message_text}")

        self.logger.info(f"Получено сообщение от пользователя {user_id} ({username}): {message_text[:50]}...")

        # Проверка наличия потока для пользователя, создание нового потока при отсутствии
        if user_id not in self.threads:
            self.logger.info(f"Создание нового потока для пользователя {user_id}")
            thread_id = self.chatgpt_assistant.create_thread(user_id)
            self.threads[user_id] = thread_id
            self.save_threads()
        else:
            thread_id = self.threads[user_id]

        # Создание уникальных имен файлов для диалогов и ответов
        if not hasattr(self, 'dialogs_filename'):
            self.dialogs_filename = self.get_unique_filename(self.dialogs_dir, user_id, username, "dialogs.txt")
        if not hasattr(self, 'responses_filename'):
            self.responses_filename = self.get_unique_filename(self.responses_dir, user_id, username, "response.txt")
        if not hasattr(self, 'emails_filename'):
            self.emails_filename = self.get_unique_filename(self.emails_dir, user_id, username, "email.html")

        try:
            self.logger.info(f"Отправка сообщения ChatGPT для пользователя {user_id}")
            response = await self.chatgpt_assistant.get_response(message_text, thread_id, user_id)
            self.logger.info(f"Получен ответ от ChatGPT для пользователя {user_id}")

            # Добавляем ответ ChatGPT в диалог
            self.dialogs[user_id].append(f"ChatGPT: {response}")

            # Сохранение диалога в файл
            await self.save_dialogs(self.dialogs_filename, self.dialogs[user_id], username)

            # Сохранение ответа в файл, если это ответ с контактной информацией
            if "Спасибо, что обратились в КлинингУМамы!" in response:
                await self.save_response(self.responses_filename, response.splitlines(), self.dialogs[user_id], username)
                # Извлекаем контактную информацию из ответа
                contact_info = self.extract_contact_info(response)
                self.send_email(user_id, username, contact_info)  # Добавляем username в параметры

            await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
        except Exception as e:
            self.logger.error(f"Ошибка при обработке сообщения для пользователя {user_id}: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Извините, произошла ошибка при обработке вашего сообщения. Попробуйте позже."
            )

    async def save_dialogs(self, filename, dialog_lines, username):
        """Сохраняет диалог в HTML файл"""
        async with aiofiles.open(os.path.join(self.dialogs_dir, filename), "w") as file:
            # Начало HTML разметки
            await file.write('<!DOCTYPE html>\n<html>\n<head>\n')
            await file.write('<meta charset="UTF-8">\n')
            await file.write(f'<title>Dialog with {username}</title>\n')
            await file.write('<style>\n')
            await file.write('body { font-family: Arial, sans-serif; margin: 20px; }\n')
            await file.write('.message { margin: 10px 0; }\n')
            await file.write('.user { color: blue; }\n')
            await file.write('.assistant { color: green; }\n')
            await file.write('</style>\n</head>\n<body>\n')
            
            # Добавляем каждое сообщение с соответствующим форматированием
            for line in dialog_lines:
                css_class = 'user' if line.startswith('User:') else 'assistant'
                await file.write(f'<div class="message {css_class}">{line}</div>\n')
            
            # Конец HTML разметки
            await file.write('</body></html>')

    async def save_response(self, filename, response_lines, dialog_lines, username):
        """Сохраняет ответ в HTML файл вместе с диалогом"""
        async with aiofiles.open(os.path.join(self.responses_dir, filename), "w") as file:
            # Начало HTML разметки
            await file.write('<!DOCTYPE html>\n<html>\n<head>\n')
            await file.write('<meta charset="UTF-8">\n')
            await file.write(f'<title>Response for {username}</title>\n')
            await file.write('<style>\n')
            await file.write('body { font-family: Arial, sans-serif; margin: 20px; }\n')
            await file.write('.response { color: green; margin: 20px 0; }\n')
            await file.write('.dialog { margin-top: 30px; }\n')
            await file.write('.message { margin: 10px 0; }\n')
            await file.write('</style>\n</head>\n<body>\n')
            
            # Добавляем ответ
            await file.write('<div class="response">\n')
            for line in response_lines:
                await file.write(f'<p>{line}</p>\n')
            await file.write('</div>\n')
            
            # Добавляем диалог
            await file.write('<div class="dialog">\n<h2>Dialog History:</h2>\n')
            for line in dialog_lines:
                await file.write(f'<div class="message">{line}</div>\n')
            await file.write('</div>\n')
            
            # Конец HTML разметки
            await file.write('</body></html>')

    def load_threads(self):
        if os.path.exists('threads.json'):
            with open('threads.json', 'r') as file:
                try:
                    threads = json.load(file)
                    self.logger.info(f"Loaded threads: {threads}")
                    # Ensure all keys in threads are strings
                    return {str(key): value for key, value in threads.items()}
                except json.JSONDecodeError:
                    self.logger.error("Failed to decode threads.json")
                    return {}
        return {}

    def save_threads(self):
        with open('threads.json', 'w') as file:
            json.dump(self.threads, file, indent=4)
        self.logger.info(f"Saved threads: {self.threads}")

    def extract_contact_info(self, response):
        """Извлекает контактную информацию из ответа"""
        lines = response.split('\n')
        contact_info = {}
        
        for line in lines:
            if 'Имя:' in line:
                contact_info['name'] = line.split('Имя:')[1].strip()
            elif 'Номер:' in line:
                contact_info['phone_number'] = line.split('Номер:')[1].strip()
            elif 'Время связи:' in line:
                contact_info['preferred_call_time'] = line.split('Время связи:')[1].strip()
        
        return contact_info

    def send_email(self, user_id, username, contact_info=None):
        self.logger.info(f"Starting send_email for user_id: {user_id}, username: {username}, contact_info: {contact_info}")
        
        # Set up the email server and login details
        smtp_server = 'smtp.mail.ru'
        smtp_port = 587
        smtp_user = os.getenv('SMTP_USER')
        smtp_password = os.getenv('SMTP_PASSWORD')
        
        self.logger.info(f"SMTP configuration - Server: {smtp_server}, Port: {smtp_port}, User: {smtp_user}")
        
        if not all([smtp_user, smtp_password]):
            self.logger.error("Missing SMTP credentials in environment variables")
            return

        # Create the email
        msg = MIMEMultipart('alternative')
        msg['From'] = smtp_user
        msg['To'] = 'da1212112@gmail.com'
        
        if contact_info:
            self.logger.info("Preparing email for contact information")
            msg['Subject'] = f"Новый заказ от пользователя {user_id}"

            # Форматируем диалог с отступами
            dialog_text = []
            if user_id in self.dialogs:
                dialog_text = self.dialogs[user_id]

            # Формируем HTML тело письма
            html_body = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                    .section {{ margin: 20px 0; }}
                    .message {{ margin: 10px 0; }}
                    .user {{ color: blue; }}
                    .assistant {{ color: green; }}
                </style>
            </head>
            <body>
                <div class="section">
                    <h2>Заказ</h2>
                    <p><strong>Клиент:</strong> {user_id} (@{username})</p>
                    <p>Спасибо, что обратились в КлинингУМамы!</p>
                    <p><strong>Имя:</strong> {contact_info.get('name', '')}</p>
                    <p><strong>Номер:</strong> {contact_info.get('phone_number', '')}</p>
                    <p><strong>Время связи:</strong> {contact_info.get('preferred_call_time', '')}</p>
                    <p>Ваш персональный менеджер скоро с вами свяжется!</p>
                </div>
                <div class="section">
                    <h2>Диалог с клиентом</h2>
                    {''.join(f'<div class="message {("user" if "User:" in msg else "assistant")}">{msg}</div>' for msg in dialog_text)}
                </div>
            </body>
            </html>
            """

            # Создаем текстовую версию для клиентов без поддержки HTML
            text_body = f"""
            Заказ

            Клиент: {user_id} (@{username})

            Спасибо, что обратились в КлинингУМамы!

            Имя: {contact_info.get('name', '')}

            Номер: {contact_info.get('phone_number', '')}

            Время связи: {contact_info.get('preferred_call_time', '')}

            Ваш персональный менеджер скоро с вами свяжется!

            Диалог с клиентом:

            {chr(10).join(dialog_text)}
            """

            # Сохраняем email сообщение в файл
            email_filename = self.get_unique_filename(self.emails_dir, user_id, username, "email.html")
            with open(os.path.join(self.emails_dir, email_filename), 'w', encoding='utf-8') as f:
                f.write(html_body)

            # Добавляем обе версии в письмо
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)

            self.logger.info(f"Contact info email body prepared and saved to {email_filename}")
        else:
            self.logger.info("Preparing email for regular response")
            msg['Subject'] = f"ChatGPT Response for User {user_id}"

            # Форматируем диалог с отступами
            dialog_text = []
            if user_id in self.dialogs:
                dialog_text = self.dialogs[user_id]

            # Формируем HTML тело письма для обычного ответа
            html_body = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                    .section {{ margin: 20px 0; }}
                    .message {{ margin: 10px 0; }}
                    .user {{ color: blue; }}
                    .assistant {{ color: green; }}
                </style>
            </head>
            <body>
                <div class="section">
                    <h2>Диалог с пользователем @{username}</h2>
                    {''.join(f'<div class="message {("user" if "User:" in msg else "assistant")}">{msg}</div>' for msg in dialog_text)}
                </div>
            </body>
            </html>
            """

            # Создаем текстовую версию
            text_body = f"""
            Диалог с пользователем @{username}:

            {chr(10).join(dialog_text)}
            """

            # Сохраняем email сообщение в файл
            email_filename = self.get_unique_filename(self.emails_dir, user_id, username, "email.html")
            with open(os.path.join(self.emails_dir, email_filename), 'w', encoding='utf-8') as f:
                f.write(html_body)

            # Добавляем обе версии в письмо
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)

            self.logger.info(f"Regular response email prepared and saved to {email_filename}")
        
        try:
            # Connect to the SMTP server and send the email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
                self.logger.info("Email sent successfully")
        except Exception as e:
            self.logger.error(f"Error sending email: {e}")
