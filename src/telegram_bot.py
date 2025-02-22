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
from telegram import Update
from telegram.ext import Application, CommandHandler, filters, MessageHandler

# Локальные импорты
from src.chatgpt_assistant import ChatGPTAssistant
from src.database import Database
from src.daily_report import DailyReport
from src.config import CONFIG

class TelegramBot:
    def __init__(self):
        self.token = CONFIG.TELEGRAM.BOT_TOKEN
        self.application = Application.builder().token(self.token).build()
        self.logger = logging.getLogger(__name__)
        self.dialogs = {}  # Будет хранить список сообщений для каждого пользователя
        self.threads = self.load_threads()
        self.file_lock = asyncio.Lock()
        self.usernames = {}  # Словарь для хранения username'ов пользователей
        self.db = Database()  # Инициализация базы данных

        # Email configuration
        self.smtp_server = CONFIG.SMTP.SERVER
        self.smtp_port = CONFIG.SMTP.PORT
        self.smtp_username = CONFIG.SMTP.USERNAME
        self.smtp_password = CONFIG.SMTP.PASSWORD
        self.notification_email = CONFIG.SMTP.NOTIFICATION_EMAIL

        # Создаем ChatGPTAssistant после инициализации всех необходимых атрибутов
        self.chatgpt_assistant = ChatGPTAssistant(telegram_bot=self)
        
        # Инициализируем планировщик отчетов
        self.daily_report = None

    async def initialize(self):
        """
        Асинхронная инициализация компонентов бота.
        """
        await self.db.init_db()
        # Инициализируем планировщик отчетов
        self.daily_report = DailyReport(telegram_bot=self)
        # Запускаем планировщик отчетов и отправляем тестовый отчет
        await self.daily_report.main()

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
        self.logger.info("Настройка телеграм-бота...")
        
        # Инициализируем базу данных и планировщик перед запуском бота
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.initialize())
        
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
        
        self.logger.info("Запуск телеграм-бота...")
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
        self.logger.info(f"Пользователь {user_id} запустил бота")
        await update.message.reply_text(
            text="Добрый день, на связи Коливинг. Для дальнейшего диалога расскажите коротко о себе."
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
        self.logger.info(f"Пользователь {user_id} запросил помощь")
        help_text = "Доступные команды:\n/start - Начать диалог\n/help - Показать это сообщение\n"
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
                f"User: {message_text}"
            )
            
            self.logger.info(
                f"Получено сообщение от пользователя {user_id} ({username}): {message_text[:50]}..."
            )

            thread_id = self.threads.get(str(user_id))
            if thread_id is None:
                self.logger.info(
                    f"Создание нового потока для пользователя {user_id}"
                )
                thread_id = self.chatgpt_assistant.create_thread(user_id=user_id)
                self.threads[str(user_id)] = thread_id
                self.save_threads()

            try:
                self.logger.info(
                    f"Отправка сообщения ChatGPT для пользователя {user_id}"
                )
                response = await self.chatgpt_assistant.get_response(
                    user_message=message_text,
                    thread_id=thread_id,
                    user_id=str(user_id)
                )
                self.logger.info(
                    f"Получен ответ от ChatGPT для пользователя {user_id}"
                )

                # Сохраняем ответ ассистента в базу данных
                await self.db.save_message(
                    user_id=user_id,
                    username=username,
                    message=response,
                    role='assistant'
                )

                self.dialogs[user_id].append(
                    f"ChatGPT: {response}"
                )

                await update.message.reply_text(
                    text=response,
                    parse_mode='HTML'
                )
                
            except Exception as e:
                self.logger.error(f"Ошибка при получении ответа от ChatGPT: {str(e)}")
                await update.message.reply_text(
                    text=f"Произошла ошибка при обработке вашего сообщения: {str(e)}"
                )
                
        except Exception as e:
            self.logger.error(f"Ошибка при обработке сообщения: {str(e)}")
            await update.message.reply_text(
                text=f"Произошла ошибка при обработке вашего сообщения: {str(e)}"
            )

    def load_threads(self):
        """
        Загружает сохраненные потоки из файла.

        Returns
        -------
        Dict[str, str]
            Словарь с потоками, где ключ - ID пользователя, значение - ID потока.
        """
        if os.path.exists('threads.json'):
            with open('threads.json', 'r') as file:
                try:
                    threads = json.load(file)
                    self.logger.info(f"Loaded threads: {threads}")
                    return {str(key): value for key, value in threads.items()}
                except json.JSONDecodeError as e:
                    self.logger.error(f"Ошибка декодирования threads.json: {str(e)}")
                    return {}
        return {}

    def save_threads(self):
        """
        Сохраняет текущие потоки в файл.
        """
        with open('threads.json', 'w') as file:
            try:
                json.dump(self.threads, file, indent=4)
                self.logger.info(f"Saved threads: {self.threads}")
            except (TypeError, ValueError) as e:
                self.logger.error(f"Ошибка сохранения потоков: {str(e)}")

    async def send_smtp_message(self, msg):
        """
        Отправляет сообщение через SMTP-сервер.

        Parameters
        ----------
        msg : MIMEMultipart
            Подготовленное сообщение.
        """
        try:
            async with asyncio.Lock():  # Защищаем отправку email
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: self._send_email(msg))
                self.logger.info("Email sent successfully")
        except Exception as e:
            self.logger.error(f"Ошибка при отправке письма: {str(e)}")
            
    def _send_email(self, msg):
        """Внутренний метод для отправки email через SMTP"""
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)

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
        
        self.logger.info(f"Начинаем отправку письма для user_id: {user_id}, username: {username}")
        
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
        msg['Subject'] = f"Новый заказ от пользователя {username}"
        
        template = self.create_email_template()
        html_body = template.substitute(
            user_id=user_id,
            username=username,
            name=contact_info.get('name', ''),
            phone=contact_info.get('phone_number', ''),
            dialog=self.format_dialog(dialog_text)
        )

        text_part = MIMEText(html_body.replace('<br>', '\n'), 'plain')
        html_part = MIMEText(html_body, 'html')
        msg.attach(text_part)
        msg.attach(html_part)

        await self.send_smtp_message(msg)
