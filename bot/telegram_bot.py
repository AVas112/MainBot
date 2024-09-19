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

    def run(self):
        """Set up and run the bot."""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))

        # Message handler
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Start the bot
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    async def start(self, update: Update, context):
        """Send a message when the command /start is issued."""
        await update.message.reply_text('Hello! I am a ChatGPT-powered Telegram bot. How can I assist you today?')

    async def help(self, update: Update, context):
        """Send a message when the command /help is issued."""
        help_text = (
            "Here are the available commands:\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n\n"
            "You can also send me any message, and I'll respond using ChatGPT!"
        )
        await update.message.reply_text(help_text)

    async def handle_message(self, update: Update, context):
        """Handle incoming messages and respond using ChatGPT."""
        user_message = update.message.text
        chat_id = update.effective_chat.id

        try:
            response = self.chatgpt_assistant.get_response(user_message)
            await context.bot.send_message(chat_id=chat_id, text=response)
        except Exception as e:
            logging.error(f"Error while processing message: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="I'm sorry, but I encountered an error while processing your message. Please try again later."
            )
