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
        self.application.add_handler(CommandHandler("change_model", self.change_model))
        self.application.add_handler(CommandHandler("set_max_tokens", self.set_max_tokens))

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
            "/help - Show this help message\n"
            "/change_model - Change the ChatGPT model (available models: gpt-4o-mini, gpt-4o)\n"
            "/set_max_tokens <number> - Set the maximum number of tokens for responses\n\n"
            "You can also send me any message, and I'll respond using ChatGPT!"
        )
        await update.message.reply_text(help_text)

    async def change_model(self, update: Update, context):
        """Change the ChatGPT model."""
        available_models = self.chatgpt_assistant.get_available_models()
        model_list = "\n".join(available_models)
        message = f"Available models:\n{model_list}\n\nTo change the model, reply with the model name."
        await update.message.reply_text(message)
        context.user_data['awaiting_model_change'] = True

    async def set_max_tokens(self, update: Update, context):
        """Set the maximum number of tokens for responses."""
        if context.args and context.args[0].isdigit():
            max_tokens = int(context.args[0])
            self.chatgpt_assistant.set_max_tokens(max_tokens)
            await update.message.reply_text(f"Maximum tokens set to {max_tokens}")
        else:
            await update.message.reply_text("Please provide a valid number of tokens. Usage: /set_max_tokens <number>")

    async def handle_message(self, update: Update, context):
        """Handle incoming messages and respond using ChatGPT."""
        user_message = update.message.text
        chat_id = update.effective_chat.id

        if context.user_data.get('awaiting_model_change', False):
            if user_message in self.chatgpt_assistant.get_available_models():
                self.chatgpt_assistant.set_model(user_message)
                await context.bot.send_message(chat_id=chat_id, text=f"Model changed to {user_message}")
            else:
                await context.bot.send_message(chat_id=chat_id, text="Invalid model name. Please try again.")
            context.user_data['awaiting_model_change'] = False
            return

        try:
            response = await self.chatgpt_assistant.get_response(user_message)
            await context.bot.send_message(chat_id=chat_id, text=response)
        except Exception as e:
            logging.error(f"Error while processing message: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="I'm sorry, but I encountered an error while processing your message. Please try again later."
            )
