import asyncio
import json
import logging
import os

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.chatgpt_assistant import ChatGPTAssistant
from src.config import CONFIG
from src.daily_report import DailyReport
from src.database import Database
from src.reminder_service import ReminderService
from src.telegram_notifications import notify_admin_about_new_dialog
from src.utils.email_service import email_service


class TelegramBot:
    def __init__(self):
        self.token = CONFIG.TELEGRAM.BOT_TOKEN
        self.application = Application.builder().token(self.token).build()
        self.bot = self.application.bot
        self.logger = logging.getLogger(__name__)
        self.dialogs = {}
        self.threads = self.load_threads()
        self.file_lock = asyncio.Lock()
        self.usernames = {}
        self.db = Database()

        self.chatgpt_assistant = ChatGPTAssistant(telegram_bot=self)
        
        self.daily_report = None
        self.reminder_service = None

    async def initialize(self):
        """Asynchronous initialization of bot components."""
        await self.db.init_db()
        self.daily_report = DailyReport(telegram_bot=self)
        await self.daily_report.main()
        

        self.reminder_service = ReminderService(
            telegram_bot=self,
            db=self.db,
            chatgpt_assistant=self.chatgpt_assistant
        )
        await self.reminder_service.start()

    def run(self):
        """
        Starts the Telegram bot and sets up command handlers.

        Notes
        -----
        The method initializes the main command handlers:
        - /start : Start interacting with the bot
        - /help : Get help
        - text messages : Handling text messages
        """
        self.logger.info("Setting up Telegram bot...")
        
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
        
        self.logger.info("Starting Telegram bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    async def start(self, update: Update, context):
        """
        Handles the /start command.

        Parameters
        ----------
        update : Update
            Update object from Telegram.
        context : CallbackContext
            Handler context.
        """
        user_id = update.effective_user.id
        self.logger.info(f"User {user_id} started the bot")
        await update.message.reply_text(
            text="Добро пожаловать в Школу продаж полного цикла! "
                 "Я - ваш ИИ‑продавец: задам пару вопросов,подсвечу точки роста. "
                 "Готовы включить турбо‑режим продаж?"
        )

    async def help(self, update: Update, context):
        """
        Handles the /help command.

        Parameters
        ----------
        update : Update
            Update object from Telegram.
        context : CallbackContext
            Handler context.
        """
        user_id = update.effective_user.id
        self.logger.info(f"User {user_id} requested help")
        help_text = "Available commands:\n/start - Start dialog\n/help - Show this message\n"
        await update.message.reply_text(text=help_text)

    async def handle_message(self, update: Update, context):
        """
        Handles incoming text messages.

        Parameters
        ----------
        update : Update
            Update object from Telegram.
        context : CallbackContext
            Handler context.

        Notes
        -----
        The method saves the dialog history and processes messages via ChatGPT.
        """
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or str(user_id)
            message_text = update.message.text

            self.usernames[user_id] = username

            if self.dialogs.get(user_id) is None:
                self.dialogs[user_id] = []

            if not await self.db.is_user_registered(user_id=user_id):
                await self.db.register_user(
                    user_id=user_id,
                    username=username,
                    first_seen=update.message.date.isoformat()
                )
                await notify_admin_about_new_dialog(self.application.bot, user_id, username)

            await self.db.save_message(
                user_id=user_id,
                username=username,
                message=message_text,
                role="user"
            )
            
            self.dialogs[user_id].append(
                f"User: {message_text}"
            )
            
            self.logger.info(
                f"Received message from user {user_id} ({username}): {message_text[:50]}..."
            )

            thread_id = self.threads.get(str(user_id))
            if thread_id is None:
                self.logger.info(
                    f"Creating new thread for user {user_id}"
                )
                thread_id = self.chatgpt_assistant.create_thread(user_id=user_id)
                self.threads[str(user_id)] = thread_id
                self.save_threads()

            try:
                self.logger.info(
                    f"Sending message to ChatGPT for user {user_id}"
                )
                response = await self.chatgpt_assistant.get_response(
                    user_message=message_text,
                    thread_id=thread_id,
                    user_id=str(user_id)
                )
                self.logger.info(
                    f"Received response from ChatGPT for user {user_id}"
                )

                await self.db.save_message(
                    user_id=user_id,
                    username=username,
                    message=response,
                    role="assistant"
                )

                self.dialogs[user_id].append(
                    f"ChatGPT: {response}"
                )

                await update.message.reply_text(
                    text=response,
                    parse_mode="HTML"
                )
                
            except Exception as e:
                self.logger.error(f"Error getting response from ChatGPT: {str(e)}")
                await update.message.reply_text(
                    text=f"An error occurred while processing your message: {str(e)}"
                )
                
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
            await update.message.reply_text(
                text=f"An error occurred while processing your message: {str(e)}"
            )

    def load_threads(self):
        """
        Loads saved threads from the file.

        Returns
        -------
        Dict[str, str]
            Dictionary with threads, where key is user ID, value is thread ID.
        """
        if os.path.exists("threads.json"):
            with open("threads.json") as file:
                try:
                    threads = json.load(file)
                    self.logger.info(f"Loaded threads: {threads}")
                    return {str(key): value for key, value in threads.items()}
                except json.JSONDecodeError as e:
                    self.logger.error(f"Error decoding threads.json: {str(e)}")
                    return {}
        return {}

    def save_threads(self):
        """Saves current threads to the file."""
        with open("threads.json", "w") as file:
            try:
                json.dump(self.threads, file, indent=4)
                self.logger.info(f"Saved threads: {self.threads}")
            except (TypeError, ValueError) as e:
                self.logger.error(f"Error saving threads: {str(e)}")

    async def send_email(self, user_id: int, contact_info: dict = None):
        """
        Sends an email with dialog information and saves the successful dialog to the database.

        Parameters
        ----------
        user_id : int
            User ID.
        contact_info : dict
            User contact information from ChatGPT Assistant.
        """
        username = f"@{self.usernames.get(user_id, str(user_id))}"
        
        dialog_text = await self.db.get_dialog(user_id=user_id)
        
        await email_service.send_telegram_dialog_email(
            user_id=user_id,
            username=username,
            contact_info=contact_info,
            dialog_text=dialog_text
        )
