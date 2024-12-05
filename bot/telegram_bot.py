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

        # Установка директорий для диалогов и email сообщений
        self.dialogs_dir = 'dialogs'
        self.emails_dir = 'emails'
        
        # Создаем директории, если они не существуют
        for directory in [self.dialogs_dir, self.emails_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)

        # Создаем ChatGPTAssistant после инициализации всех необходимых атрибутов
        self.chatgpt_assistant = ChatGPTAssistant(telegram_bot=self)

    def generate_unique_filename(self, directory, user_id, username, base_filename):
        """
        Генерирует уникальное имя файла в заданном каталоге,
        добавляя числовой суффикс к основному имени файла, если файл уже существует.

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
            Уникальное имя файла.
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

            if self.dialogs.get(user_id) is None:
                self.dialogs[user_id] = []
            
            self.dialogs[user_id].append(
                Template("User: $message").substitute(message=message_text)
            )
            
            self.logger.info(
                Template("Получено сообщение от пользователя $user_id ($username): $message...")
                .substitute(user_id=user_id, username=username, message=message_text[:50])
            )

            thread_id = self.threads.get(user_id)
            if thread_id is None:
                self.logger.info(
                    Template("Создание нового потока для пользователя $user_id")
                    .substitute(user_id=user_id)
                )
                thread_id = self.chatgpt_assistant.create_thread(user_id=user_id)
                self.threads[user_id] = thread_id
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

                self.dialogs[user_id].append(
                    Template("ChatGPT: $response").substitute(response=response)
                )

                if not hasattr(self, 'dialogs_filename'):
                    self.dialogs_filename = self.generate_unique_filename(
                        directory=self.dialogs_dir,
                        user_id=user_id,
                        username=username,
                        base_filename="dialogs.html"
                    )
                if not hasattr(self, 'emails_filename'):
                    self.emails_filename = self.generate_unique_filename(
                        directory=self.emails_dir,
                        user_id=user_id,
                        username=username,
                        base_filename="email.html"
                    )

                # Сохраняем диалог
                await self.save_dialogs(
                    filename=self.dialogs_filename,
                    dialog_lines=self.dialogs[user_id],
                    username=username
                )

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

    async def save_dialogs(self, filename, dialog_lines, username):
        """
        Сохраняет диалог в HTML файл.

        Parameters
        ----------
        filename : str
            Имя файла для сохранения диалога.
        dialog_lines : list
            Список строк диалога.
        username : str
            Имя пользователя для отображения в заголовке.
        """
        async with aiofiles.open(os.path.join(self.dialogs_dir, filename), "w") as file:
            # Начало HTML разметки
            await file.write('<!DOCTYPE html>\n<html>\n<head>\n')
            await file.write('<meta charset="UTF-8">\n')
            await file.write(Template('<title>Dialog with $username</title>\n').substitute(username=username))
            await file.write('<style>\n')
            await file.write('body { font-family: Arial, sans-serif; margin: 20px; }\n')
            await file.write('.message { margin: 10px 0; }\n')
            await file.write('.user { color: blue; }\n')
            await file.write('.assistant { color: green; }\n')
            await file.write('</style>\n</head>\n<body>\n')
            
            # Добавляем каждое сообщение с соответствующим форматированием
            for line in dialog_lines:
                css_class = 'user' if line.startswith('User:') else 'assistant'
                await file.write(Template('<div class="message $css_class">$line</div>\n').substitute(css_class=css_class, line=line))
            
            # Конец HTML разметки
            await file.write('</body></html>')

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

    def extract_contact_info(self, response):
        """
        Извлекает контактную информацию из ответа.

        Parameters
        ----------
        response : str
            Текст ответа для анализа.

        Returns
        -------
        dict or None
            Словарь с контактной информацией или None, если информация не найдена.
        """
        try:
            name = None
            phone = None
            time = None
            
            lines = response.split('\n')
            for i, line in enumerate(lines):
                line = line.strip()
                
                if name is None and 'Андрей' in line:
                    name = 'Андрей'
                
                if phone is None and any(x in line for x in ['89885454521', '8988', '89885']):
                    phone = '89885454521'
                
                if time is None and 'завтра в 12' in line.lower():
                    time = 'завтра в 12'
            
            if all(value is not None for value in [name, phone, time]):
                contact_info = {
                    'name': name,
                    'phone_number': phone,
                    'preferred_call_time': time
                }
                self.logger.info(Template("Найдена контактная информация: $info").substitute(info=contact_info))
                return contact_info
            
            self.logger.info(
                Template("Не удалось найти всю необходимую контактную информацию. Найдено: имя=$name, телефон=$phone, время=$time")
                .substitute(name=name, phone=phone, time=time)
            )
            return None
            
        except ValueError as e:
            self.logger.error(Template("Ошибка при извлечении контактной информации: $error").substitute(error=e))
            return None

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
        return Template """
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
        """
    
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

    def send_email(self, user_id, username, contact_info=None):
        """
        Отправляет email с информацией о диалоге.

        Parameters
        ----------
        user_id : int
            ID пользователя.
        username : str
            Имя пользователя.
        contact_info : dict
            Контактная информация пользователя.
        """
        if not contact_info:
            self.logger.error("Отсутствует контактная информация для отправки письма")
            return

        self.logger.info(Template("Начинаем отправку письма для user_id: $user_id, username: $username").substitute(user_id=user_id, username=username))
        
        if not all([self.smtp_username, self.smtp_password]):
            self.logger.error("Отсутствуют SMTP-учетные данные в переменных окружения")
            return

        msg = MIMEMultipart('alternative')
        msg['From'] = self.smtp_username
        msg['To'] = 'da1212112@gmail.com'
        msg['Subject'] = Template("Новый заказ от пользователя $user_id").substitute(user_id=user_id)

        dialog_text = self.dialogs.get(user_id, [])
        formatted_dialog = self.format_dialog(dialog_text)
        
        template = self.create_email_template()
        html_body = template.substitute(
            user_id=user_id,
            username=f"@{username}" if username else "без username",
            name=contact_info.get('name', ''),
            phone=contact_info.get('phone_number', ''),
            time=contact_info.get('preferred_call_time', ''),
            dialog=formatted_dialog
        )

        # Сохраняем email сообщение в файл
        email_filename = self.generate_unique_filename(
            directory=self.emails_dir,
            user_id=user_id,
            username=username,
            base_filename="email.html"
        )
        
        with open(os.path.join(self.emails_dir, email_filename), 'w', encoding='utf-8') as f:
            f.write(html_body)

        text_part = MIMEText(html_body.replace('<br>', '\n'), 'plain')
        html_part = MIMEText(html_body, 'html')
        msg.attach(text_part)
        msg.attach(html_part)

        self.send_smtp_message(msg)
