import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from .chatgpt_assistant import ChatGPTAssistant

class TelegramBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chatgpt_assistant = ChatGPTAssistant()
        self.application = Application.builder().token(self.token).build()
        self.logger = logging.getLogger(__name__)
        self.dialogs = {}

    def run(self):
        self.logger.info("Setting up Telegram bot...")
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.logger.info("Starting Telegram bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    async def start(self, update: Update, context):
        self.logger.info(f"User {update.effective_user.id} started the bot")
        await update.message.reply_text('Привет. Я консультат компании КлинингУМамы. Чем я могу вам помочь?')

    async def help(self, update: Update, context):
        self.logger.info(f"User {update.effective_user.id} requested help")
        help_text = (
            "Here are the available commands:\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "You can also send me any message, and I'll respond using ChatGPT!"
        )
        await update.message.reply_text(help_text)

    async def handle_message(self, update: Update, context):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        user_message = update.message.text

        self.logger.info(f"Received message from user {user_id}: {user_message[:50]}...")

        # Initialize dialog if not present
        if user_id not in self.dialogs:
            self.dialogs[user_id] = []

        # Append user message to the dialog
        self.dialogs[user_id].append(f"User: {user_message}")

        try:
            self.logger.info(f"Sending message to ChatGPT for user {user_id}")
            response = await self.chatgpt_assistant.get_response(user_message)
            self.logger.info(f"Received response from ChatGPT for user {user_id}")

            # Append ChatGPT response to the dialog
            self.dialogs[user_id].append(f"ChatGPT: {response}")

            # Check if the response contains the target phrase
            if "Спасибо за обращение к нам!" in response:
                response_lines = response.split('\n')
                target_index = next((i for i, line in enumerate(response_lines)
                                     if "Спасибо за обращение к нам!" in line), None)
                if target_index is not None:
                    following_lines = response_lines[target_index + 1: target_index + 4]
                    self.save_response(following_lines, user_id)
                    self.send_email(user_id)

            await context.bot.send_message(chat_id=chat_id, text=response)
        except Exception as e:
            self.logger.error(f"Error while processing message for user {user_id}: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="I'm sorry, but I encountered an error while processing your message. Please try again later."
            )

    def save_response(self, lines, user_id):
        # Save the following lines when "Спасибо за обращение к нам!" is found
        with open(f"responses/{user_id}_response.txt", "w") as file:
            for line in lines:
                file.write(line + '\n')

    def send_email(self, user_id):
        # Set up the email server and login details
        smtp_server = 'smtp.mail.ru'
        smtp_port = 587
        smtp_user = os.getenv('SMTP_USER')
        smtp_password = os.getenv('SMTP_PASSWORD')

        # Create the email
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = 'da1212112@gmail.com'
        msg['Subject'] = f"ChatGPT Response for User {user_id}"

        # Attach the dialog and saved response
        dialog = "\n".join(self.dialogs[user_id])
        with open(f"responses/{user_id}_response.txt", "r") as file:
            saved_response = file.read()

        msg.attach(MIMEText(f"Full dialog:\n\n{dialog}\n\nSaved response:\n\n{saved_response}", 'plain'))

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


