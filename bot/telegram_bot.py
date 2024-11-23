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
from bot.chatgpt_assistant import ChatGPTAssistant
from datetime import datetime

class TelegramBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chatgpt_assistant = ChatGPTAssistant()
        self.application = Application.builder().token(self.token).build()
        self.logger = logging.getLogger(__name__)
        self.dialogs = {}
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
        user = update.effective_user  # Извлекаем информацию о пользователе
        username = user.username if user.username else 'Unknown'  # Извлекаем логин или устанавливаем значение 'Unknown'
        user_id = str(user.id)  # Убедитесь, что user_id - строка
        chat_id = update.effective_chat.id
        user_message = update.message.text

        self.logger.info(f"Получено сообщение от пользователя {user_id} ({username}): {user_message[:50]}...")

        # Инициализация диалога, если он отсутствует
        if user_id not in self.dialogs:
            self.dialogs[user_id] = []

        # Проверка наличия потока для пользователя, создание нового потока при отсутствии
        if user_id not in self.threads:
            self.logger.info(f"Создание нового потока для пользователя {user_id}")
            thread_id = self.chatgpt_assistant.create_thread(user_id)
            self.logger.info(f"Создан ID потока {thread_id} для пользователя {user_id}")
            self.threads[user_id] = thread_id
            self.save_threads()
        else:
            thread_id = self.threads[user_id]
            self.logger.info(f"Использование существующего ID потока {thread_id} для пользователя {user_id}")

        # Устанавливаем уникальные имена файлов для текущей пользовательской сессии
        if not hasattr(self, 'dialogs_filename'):
            self.dialogs_filename = self.get_unique_filename(self.dialogs_dir, user_id, username, "dialogs.txt")
        if not hasattr(self, 'responses_filename'):
            self.responses_filename = self.get_unique_filename(self.responses_dir, user_id, username, "response.txt")

        # Добавление сообщения пользователя в диалог
        self.dialogs[user_id].append(f"User: {user_message}")

        try:
            self.logger.info(f"Отправка сообщения ChatGPT для пользователя {user_id}")
            response = await self.chatgpt_assistant.get_response(user_message, thread_id, user_id)
            self.logger.info(f"Получен ответ от ChatGPT для пользователя {user_id}")

            # Добавление ответа ChatGPT в диалог
            self.dialogs[user_id].append(f"ChatGPT: {response}")

            # Сохранение диалога в файл
            await self.save_dialogs(self.dialogs_filename, self.dialogs[user_id], username)

            # Проверка на специфическое сообщение
            if "Спасибо, что обратились в КлинингУМамы!" in response:
                await self.save_response(self.responses_filename, response.splitlines(), self.dialogs[user_id], username)  # Асинхронный вызов
                self.send_email(user_id)  # Этот метод остается синхронным

            await context.bot.send_message(chat_id=chat_id, text=response)
        except Exception as e:
            self.logger.error(f"Ошибка при обработке сообщения для пользователя {user_id}: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="Извините, произошла ошибка при обработке вашего сообщения. Попробуйте позже."
            )

    async def save_dialogs(self, filename, dialog, username):
        async with aiofiles.open(os.path.join(self.dialogs_dir, filename), "a") as file:
            await file.write(f"Клиент: {username}\n")  # Записываем логин клиента
            await file.write('Диалог с клиентом:\n')
            for line in dialog:
                await file.write(line + "\n" + "\n")

    async def save_response(self, filename, lines, dialog, username):
        async with aiofiles.open(os.path.join(self.responses_dir, filename), "a") as file:
            # Начало HTML разметки
            await file.write('<ht<head><style>')
            await file.write('''
                body { font-family: Arial, sans-serif; line-height: 1.6; }
                   h2 { color: #2c3e50; }
                   .section { margin-bottom: 20px; }
                   .section p { margin: 5px 0; }
                   .ёclient-info { font-weight: bold; }
               ''')
            await file.write('</style></head><body>')
              # Основная часть письма
            await file.write('<div class="section"><h2>Заказ</h2></div>')
            await file.write(f'<p class="client-info">Клиент: {username}</p>')
            for line in lines:
                 await file.write(f'<p>{line}</p>')
            # Информация о клиенте и диалог
            await file.write('<div class="section"><h2>Диалог с клиентом</h2>')
            for line in dialog:
                await file.write(f'<p>{line}</p>')
            await file.write('</div>')
            # Конец HTML разметки
            await file.write('</body></html>')

    async def send_contact_notification(self, contact_info: dict, username: str):
        """
        Асинхронно отправляет уведомление о новом контакте на email
        """
        if not all([self.smtp_server, self.smtp_username, self.smtp_password, self.notification_email]):
            self.logger.error("Email configuration is incomplete")
            return

        message = MIMEMultipart()
        message["From"] = self.smtp_username
        message["To"] = self.notification_email
        message["Subject"] = f"Новый контакт от пользователя {username}"

        body = f"""
        Получена новая контактная информация:
        
        Имя клиента: {contact_info.get('name')}
        Телефон: {contact_info.get('phone_number')}
        Предпочтительное время для звонка: {contact_info.get('preferred_call_time')}
        
        Пользователь Telegram: {username}
        Время получения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """

        message.attach(MIMEText(body, "plain"))

        try:
            async with asyncio.Lock():
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)
                server.quit()
                self.logger.info(f"Contact notification email sent for user {username}")
        except Exception as e:
            self.logger.error(f"Failed to send contact notification email: {str(e)}")

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

    def send_email(self, user_id):
        # Set up the email server and login details
        smtp_server = 'smtp.mail.ru'
        smtp_port = 587
        smtp_user = os.getenv('SMTP_USER')
        smtp_password = os.getenv('SMTP_PASSWORD')
         
        # Create the email
        msg = MIMEMultipart('alternative')
        msg['From'] = smtp_user
        msg['To'] = 'da1212112@gmail.com'
        msg['Subject'] = f"ChatGPT Response for User {user_id}"
         
        # Attach the dialog and saved response
        with open(os.path.join(self.responses_dir, self.responses_filename), "r") as file:
            saved_response = file.read()
             
        part1 = MIMEText(saved_response, 'plain')
        part2 = MIMEText(saved_response, 'html')
         
        msg.attach(part1)
        msg.attach(part2)
         
        # Send the email
        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, 'da1212112@gmail.com', msg.as_string())
            server.quit()
            self.logger.info(f"Email sent successfully for user {user_id}")
        except Exception as e:
            self.logger.error(f"Failed to send email for user {user_id}: {e}")
