# Стандартные библиотеки
import asyncio
import json
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from string import Template

# Сторонние библиотеки
import aiofiles
from telegram import Update
from telegram.ext import Application, CommandHandler, filters, MessageHandler

# Локальные импорты
from bot.chatgpt_assistant import ChatGPTAssistant
from bot.database import Database

class TelegramBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.application = Application.builder().token(self.token).build()
        self.logger = logging.getLogger(__name__)
        self.dialogs = {}  # Будет хранить список сообщений для каждого пользователя
        self.threads = self.load_threads()
        self.file_lock = asyncio.Lock()
        self.usernames = {}  # Словарь для хранения username'ов пользователей
        self.db = Database()  # Инициализация базы данных

        # Email configuration
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.notification_email = os.getenv('NOTIFICATION_EMAIL')

        # Установка директорий для диалогов и email сообщений
        self.emails_dir = 'emails'
        
        # Создаем директории, если они не существуют
        if not os.path.exists(self.emails_dir):
            os.makedirs(self.emails_dir)

        # Создаем ChatGPTAssistant после инициализации всех необходимых атрибутов
        self.chatgpt_assistant = ChatGPTAssistant(telegram_bot=self)

    async def initialize(self):
        """
        Асинхронная инициализация компонентов бота.
        """
        await self.db.init_db()

    def run(self):
        """
        Запускает телеграм-бота и настраивает обработчики команд.

        Notes
        -----
        Метод инициализирует основные обработчики команд:
        - /start : Начало работы с ботом
        - /help : Получение справки
        - text messages : Обработка текстовых сообщений
        """
        self.logger.info(Template("$action").substitute(action="Настройка телеграм-бота..."))
        
        # Инициализируем базу данных перед запуском бота
        asyncio.get_event_loop().run_until_complete(self.initialize())
        
        self.application.add_handler(
            handler=CommandHandler(
                command="start",
                callback=self.start
            )
        )
        self.application.add_handler(
            handler=CommandHandler(
                command="help",
                callback=self.help
            )
        )
        self.application.add_handler(
            handler=MessageHandler(
                filters=filters.TEXT & ~filters.COMMAND,
                callback=self.handle_message
            )
        )
        
        self.logger.info(Template("$action").substitute(action="Запуск телеграм-бота..."))
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    async def start(self, update: Update, context):
        """
        Обрабатывает команду /start.

        Parameters
        ----------
        update : Update
            Объект обновления от Telegram.
        context : CallbackContext
            Контекст обработчика.
        """
        user_id = update.effective_user.id
        self.logger.info(Template("Пользователь $user_id запустил бота").substitute(user_id=user_id))
        await update.message.reply_text(
            text=Template("$greeting").substitute(
                greeting="Привет. Я консультант компании КлинингУМамы. Чем я могу вам помочь?"
            )
        )

    async def help(self, update: Update, context):
        """
        Обрабатывает команду /help.

        Parameters
        ----------
        update : Update
            Объект обновления от Telegram.
        context : CallbackContext
            Контекст обработчика.
        """
        user_id = update.effective_user.id
        self.logger.info(Template("Пользователь $user_id запросил помощь").substitute(user_id=user_id))
        help_text = Template(
            "Доступные команды:\n"
            "/start - Начать диалог\n"
            "/help - Показать это сообщение\n"
        ).substitute()
        await update.message.reply_text(text=help_text)

    async def handle_message(self, update: Update, context):
        """
        Обрабатывает входящие текстовые сообщения.

        Parameters
        ----------
        update : Update
            Объект обновления от Telegram.
        context : CallbackContext
            Контекст обработчика.

        Notes
        -----
        Метод сохраняет историю диалога и обрабатывает сообщения через ChatGPT.
        """
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or str(user_id)
            message_text = update.message.text

            # Сохраняем username пользователя
            self.usernames[user_id] = username

            if self.dialogs.get(user_id) is None:
                self.dialogs[user_id] = []
            
            # Сохраняем сообщение пользователя в базу данных
            await self.db.save_message(
                user_id=user_id,
                username=username,
                message=message_text,
                role='user'
            )
            
            self.dialogs[user_id].append(
                Template("User: $message").substitute(message=message_text)
            )
            
            self.logger.info(
                Template("Получено сообщение от пользователя $user_id ($username): $message...")
                .substitute(user_id=user_id, username=username, message=message_text[:50])
            )

            thread_id = self.threads.get(str(user_id))
            if thread_id is None:
                self.logger.info(
                    Template("Создание нового потока для пользователя $user_id")
                    .substitute(user_id=user_id)
                )
                thread_id = self.chatgpt_assistant.create_thread(user_id=user_id)
                self.threads[str(user_id)] = thread_id
                self.save_threads()

            try:
                self.logger.info(
                    Template("Отправка сообщения ChatGPT для пользователя $user_id")
                    .substitute(user_id=user_id)
                )
                response = await self.chatgpt_assistant.get_response(
                    user_message=message_text,
                    thread_id=thread_id,
                    user_id=str(user_id)
                )
                self.logger.info(
                    Template("Получен ответ от ChatGPT для пользователя $user_id")
                    .substitute(user_id=user_id)
                )

                # Сохраняем ответ ассистента в базу данных
                await self.db.save_message(
                    user_id=user_id,
                    username=username,
                    message=response,
                    role='assistant'
                )

                self.dialogs[user_id].append(
                    Template("ChatGPT: $response").substitute(response=response)
                )

                # Получаем диалог из базы данных
                dialog_lines = await self.db.get_dialog(user_id)

                # Генерируем HTML для диалога
                html_content = self.db.format_dialog_html(dialog_lines, username)

                # Сохраняем HTML в файл для email
                emails_filename = self.generate_unique_filename(
                    directory=self.emails_dir,
                    user_id=user_id,
                    username=username,
                    base_filename="email.html"
                )

                async with self.file_lock:
                    async with aiofiles.open(os.path.join(self.emails_dir, emails_filename), "w", encoding='utf-8') as file:
                        await file.write(html_content)

                await update.message.reply_text(text=response)
                
            except Exception as e:
                error_msg = Template("Ошибка при получении ответа от ChatGPT: $error").substitute(error=str(e))
                self.logger.error(error_msg)
                await update.message.reply_text(
                    text=Template("Произошла ошибка при обработке вашего сообщения: $error")
                    .substitute(error=str(e))
                )
                
        except Exception as e:
            error_msg = Template("Ошибка при обработке сообщения: $error").substitute(error=str(e))
            self.logger.error(error_msg)
            await update.message.reply_text(
                text=Template("Произошла ошибка при обработке вашего сообщения: $error")
                .substitute(error=str(e))
            )

    def load_threads(self):
        """
        Загружает информацию о потоках из файла.

        Returns
        -------
        dict
            Словарь с информацией о потоках, где ключ - id пользователя,
            значение - id потока.
        """
        if os.path.exists('threads.json'):
            with open('threads.json', 'r') as file:
                try:
                    threads = json.load(file)
                    self.logger.info(Template("Loaded threads: $threads").substitute(threads=threads))
                    return {str(key): value for key, value in threads.items()}
                except json.JSONDecodeError as e:
                    self.logger.error(Template("Ошибка декодирования threads.json: $error").substitute(error=e))
                    return {}
        return {}

    def save_threads(self):
        """
        Сохраняет информацию о потоках в файл.

        Записывает текущее состояние словаря потоков в JSON файл
        для последующего восстановления.
        """
        with open('threads.json', 'w') as file:
            try:
                json.dump(self.threads, file, indent=4)
                self.logger.info(Template("Saved threads: $threads").substitute(threads=self.threads))
            except (TypeError, ValueError) as e:
                self.logger.error(Template("Ошибка сохранения потоков: $error").substitute(error=e))

    def send_smtp_message(self, msg):
        """
        Отправляет сообщение через SMTP-сервер.

        Parameters
        ----------
        msg : MIMEMultipart
            Подготовленное сообщение.
        """
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
                self.logger.info("Email sent successfully")
        except smtplib.SMTPException as e:
            self.logger.error(Template("Ошибка при отправке письма: $error").substitute(error=e))

    def create_email_template(self):
        """
        Создает шаблон письма.

        Returns
        -------
        Template
            Шаблон письма.
        """
        return Template ("""
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; }
                .section { margin: 20px 0; }
                .message { margin: 10px 0; }
                .user { color: blue; }
                .assistant { color: green; }
            </style>
        </head>
        <body>
            <div class="section">
                <h2>Заказ</h2>
                <p><strong>Клиент:</strong> $user_id ($username)</p>
                <p>Спасибо, что обратились в КлинингУМамы!</p>
                <p><strong>Имя:</strong> $name</p>
                <p><strong>Номер:</strong> $phone</p>
                <p><strong>Время связи:</strong> $time</p>
                <p>Ваш персональный менеджер скоро с вами свяжется!</p>
            </div>
            <div class="section">
                <h2>Диалог с клиентом</h2>
                $dialog
            </div>
        </body>
        </html>
        """)
    
    def format_dialog(self, dialog_text):
        """
        Форматирует диалог для отображения в письме.

        Parameters
        ----------
        dialog_text : list
            Список сообщений диалога.

        Returns
        -------
        str
            Отформатированный HTML-код диалога.
        """
        return ''.join(Template('<div class="message $css_class">$msg</div>').substitute(css_class=("user" if "User:" in msg else "assistant"), msg=msg) 
                      for msg in dialog_text)

    async def send_email(self, user_id: int, contact_info: dict = None):
        """
        Отправляет email с информацией о диалоге и сохраняет успешный диалог в базу данных.

        Parameters
        ----------
        user_id : int
            ID пользователя.
        contact_info : dict
            Контактная информация пользователя от ChatGPT Assistant.
        """
        if not contact_info:
            self.logger.error("Отсутствует контактная информация для отправки письма")
            return

        # Используем сохраненный telegram_username если он есть, иначе ID пользователя
        username = f"@{self.usernames.get(user_id, str(user_id))}"
        
        self.logger.info(Template("Начинаем отправку письма для user_id: $user_id, username: $username").substitute(
            user_id=user_id, 
            username=username
        ))
        
        if not all([self.smtp_username, self.smtp_password]):
            self.logger.error("Отсутствуют SMTP-учетные данные в переменных окружения")
            return

        # Получаем диалог из базы данных
        dialog_text = await self.db.get_dialog(user_id)
        
        # Сохраняем успешный диалог в базу данных после получения всех данных
        try:
            await self.db.save_successful_dialog(
                user_id=user_id,
                username=username,
                contact_info=contact_info,
                messages=dialog_text
            )
            self.logger.info(f"Успешный диалог сохранен в базу данных для пользователя {username}")
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении диалога в базу данных: {str(e)}")

        # Формируем email
        msg = MIMEMultipart('alternative')
        msg['From'] = self.smtp_username
        msg['To'] = 'da1212112@gmail.com'
        msg['Subject'] = Template("Новый заказ от пользователя $name").substitute(name=username)
        
        template = self.create_email_template()
        html_body = template.substitute(
            user_id=user_id,
            username=username,
            name=contact_info.get('name', ''),
            phone=contact_info.get('phone_number', ''),
            time=contact_info.get('preferred_call_time', ''),
            dialog=self.format_dialog(dialog_text)
        )

        text_part = MIMEText(html_body.replace('<br>', '\n'), 'plain')
        html_part = MIMEText(html_body, 'html')
        msg.attach(text_part)
        msg.attach(html_part)

        self.send_smtp_message(msg)

    def generate_unique_filename(self, directory, user_id, username, base_filename):
        """
        Генерирует имя файла для пользователя.

        Parameters
        ----------
        directory : str
            Путь к директории для сохранения файла.
        user_id : int
            Идентификатор пользователя.
        username : str
            Имя пользователя.
        base_filename : str
            Базовое имя файла.

        Returns
        -------
        str
            Имя файла для пользователя.
        """
        if not os.path.exists(directory):
            os.makedirs(directory)

        # Для email используем уникальные имена, для диалогов - постоянные
        if directory == self.emails_dir:
            count = 1
            filename = f"{user_id}_{username}_{base_filename}"
            while os.path.exists(os.path.join(directory, filename)):
                filename = f"{user_id}_{username}_{base_filename}_{count}"
                count += 1
        else:
            filename = f"{user_id}_{username}_{base_filename}"
        
        return filename
