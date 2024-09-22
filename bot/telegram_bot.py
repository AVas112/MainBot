import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from .chatgpt_assistant import ChatGPTAssistant

class TelegramBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chatgpt_assistant = ChatGPTAssistant()
        self.application = Application.builder().token(self.token).build()
        self.logger = logging.getLogger(__name__)

    def run(self):
        """Set up and run the bot."""
        self.logger.info("Setting up Telegram bot...")
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))

        # Message handler
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Start the bot
        self.logger.info("Starting Telegram bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    async def start(self, update: Update, context):
        """Send a message when the command /start is issued."""
        self.logger.info(f"User {update.effective_user.id} started the bot")
        await update.message.reply_text('Привет. Я консультат компании КлинингУМамы. Чем я могу вам помочь?')

    async def help(self, update: Update, context):
        """Send a message when the command /help is issued."""
        self.logger.info(f"User {update.effective_user.id} requested help")
        help_text = (
            "Here are the available commands:\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "You can also send me any message, and I'll respond using ChatGPT!"
        )
        await update.message.reply_text(help_text)

    async def handle_message(self, update: Update, context):
        """Handle incoming messages and respond using ChatGPT."""
        user_message = update.message.text
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        self.logger.info(f"Received message from user {user_id}: {user_message[:50]}...")

        try:
            self.logger.info(f"Sending message to ChatGPT for user {user_id}")
            response = await self.chatgpt_assistant.get_response(user_message)
            self.logger.info(f"Received response from ChatGPT for user {user_id}")
            await context.bot.send_message(chat_id=chat_id, text=response)
        except Exception as e:
            self.logger.error(f"Error while processing message for user {user_id}: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="I'm sorry, but I encountered an error while processing your message. Please try again later."
            )
