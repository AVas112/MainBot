from telegram import Bot
from telegram.error import TelegramError
import logging

from src.config import CONFIG


async def notify_admin_about_new_dialog(bot: Bot, user_id: int, username: str) -> None:
    """
    Отправляет уведомление в админ-чат о новом диалоге с пользователем.
    """
    logger = logging.getLogger(__name__)
    url = f"{CONFIG.WEB_UI.BASE_URL}/admin/dialog/{user_id}"
    logger.info(f"Notify admin about new dialog with @{username}")
    text = (
        f"🔔 *Новый диалог* с пользователем @{username}\n"
        f"[Перейти к истории]({url})"
    )
    try:
        await bot.send_message(
            chat_id=CONFIG.TELEGRAM.ADMIN_CHAT_ID,
            text=text,
            parse_mode="Markdown"
        )
    except TelegramError as e:
        logging.getLogger(__name__).error(
            f"Не удалось отправить уведомление администратору: {e}"
        )


async def notify_admin_about_successful_dialog(bot: Bot, user_id: int, username: str, contact_info: dict) -> None:
    """
    Отправляет уведомление в админ-чат о новой заявке на звонок менеджера.
    """
    logger = logging.getLogger(__name__)
    url = f"{CONFIG.WEB_UI.BASE_URL}/admin/dialog/{user_id}"
    name = contact_info.get("name", "")
    phone = contact_info.get("phone_number", "")
    text = (
        "📞 *Новая заявка на звонок менеджера!*\n"
        f"*Клиент:* @{username}\n"
        f"*Имя:* {name}\n"
        f"*Телефон:* {phone}\n"
        f"[Просмотреть диалог]({url})"
    )
    try:
        logger.info(f"Notify admin about successful dialog of @{username}")
        await bot.send_message(
            chat_id=CONFIG.TELEGRAM.ADMIN_CHAT_ID,
            text=text,
            parse_mode="Markdown"
        )
    except TelegramError as e:
        logger.error(f"Не удалось отправить уведомление об успешном диалоге: {e}")
