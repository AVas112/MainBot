import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Возвращаем исходные импорты
from src.web_ui.dependencies import DatabaseDep
from src.web_ui.schemas import Dialog, Message, User


# Создание роутера
router = APIRouter(prefix="/admin", tags=["admin"])

# Инициализация шаблонизатора
templates = Jinja2Templates(directory="src/web_ui/templates")


@router.get("/", response_class=HTMLResponse)
async def get_users_list(request: Request, db: DatabaseDep):
    """Маршрут для отображения списка пользователей.
    
    Parameters
    ----------
    request : Request
        Объект запроса
    db : Database
        Экземпляр базы данных
        
    Returns
    -------
    HTMLResponse
        HTML страница со списком пользователей
    """
    # Получение списка уникальных пользователей с информацией о последнем сообщении
    users_data = await db.execute_fetch("""
        SELECT 
            d.user_id, 
            d.username, 
            MAX(d.timestamp) as last_message, 
            COUNT(d.id) as message_count 
        FROM dialogs d 
        GROUP BY d.user_id, d.username 
        ORDER BY last_message DESC
    """)
    
    # Преобразование данных в список объектов User
    users = []
    for user_id, username, last_message, message_count in users_data:
        users.append(User(
            user_id=user_id,
            username=username or "Неизвестный",
            last_message=datetime.fromisoformat(last_message) if last_message else datetime.now(),
            message_count=message_count
        ))
    
    # Получение списка успешных диалогов
    successful_dialogs = await db.execute_fetch("""
        SELECT 
            user_id, 
            username, 
            created_at 
        FROM successful_dialogs 
        ORDER BY created_at DESC
    """)
    
    successful_users = []
    for user_id, username, created_at in successful_dialogs:
        successful_users.append({
            "user_id": user_id,
            "username": username or "Неизвестный",
            "created_at": datetime.fromisoformat(created_at) if created_at else datetime.now()
        })
    
    # Проверяем, является ли запрос AJAX-запросом
    is_ajax = request.query_params.get("ajax", "").lower() == "true"
    
    # Если это AJAX-запрос, возвращаем только HTML-содержимое без базового шаблона
    if is_ajax:
        return templates.TemplateResponse(
            "users_list.html", 
            {"request": request, "users": users, "successful_users": successful_users, "is_ajax": True}
        )
    
    return templates.TemplateResponse(
        "users_list.html", 
        {"request": request, "users": users, "successful_users": successful_users, "is_ajax": False}
    )


@router.get("/dialog/{user_id}", response_class=HTMLResponse)
async def get_dialog(request: Request, user_id: int, db: DatabaseDep):
    """Маршрут для отображения диалога с пользователем.
    
    Parameters
    ----------
    request : Request
        Объект запроса
    user_id : int
        ID пользователя
    db : Database
        Экземпляр базы данных
        
    Returns
    -------
    HTMLResponse
        HTML страница с диалогом
    """
    # Получение информации о пользователе
    user_data = await db.execute_fetch("""
        SELECT username FROM dialogs 
        WHERE user_id = ? 
        LIMIT 1
    """, (user_id,))
    
    if not user_data:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    username = user_data[0][0] or "Неизвестный"
    
    # Получение сообщений диалога
    messages_data = await db.execute_fetch("""
        SELECT message, role, timestamp 
        FROM dialogs 
        WHERE user_id = ? 
        ORDER BY timestamp
    """, (user_id,))
    
    # Преобразование данных в список объектов Message
    messages = []
    for message, role, timestamp in messages_data:
        messages.append(Message(
            message=message,
            role=role,
            timestamp=datetime.fromisoformat(timestamp) if timestamp else datetime.now()
        ))
    
    # Создание объекта диалога
    dialog = Dialog(
        user_id=user_id,
        username=username,
        messages=messages
    )
    
    # Проверка, есть ли успешный диалог с этим пользователем
    successful_dialog = await db.execute_fetch("""
        SELECT id, contact_info, messages, created_at 
        FROM successful_dialogs 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT 1
    """, (user_id,))
    
    contact_info = None
    if successful_dialog:
        dialog_id, contact_info_json, messages_json, _ = successful_dialog[0]
        contact_info = json.loads(contact_info_json) if contact_info_json else None
    
    # Проверяем, является ли запрос AJAX-запросом
    is_ajax = request.query_params.get("ajax", "").lower() == "true"
    
    # Если это AJAX-запрос, возвращаем только HTML-содержимое без базового шаблона
    if is_ajax:
        return templates.TemplateResponse(
            "dialog.html", 
            {
                "request": request, 
                "dialog": dialog, 
                "contact_info": contact_info,
                "is_ajax": True
            }
        )
    
    return templates.TemplateResponse(
        "dialog.html", 
        {
            "request": request, 
            "dialog": dialog, 
            "contact_info": contact_info,
            "is_ajax": False
        }
    )


@router.get("/successful_dialogs", response_class=HTMLResponse)
async def get_successful_dialogs(request: Request, db: DatabaseDep):
    """Маршрут для отображения списка успешных диалогов.
    
    Parameters
    ----------
    request : Request
        Объект запроса
    db : Database
        Экземпляр базы данных
        
    Returns
    -------
    HTMLResponse
        HTML страница со списком успешных диалогов
    """
    # Получение списка успешных диалогов
    dialogs_data = await db.execute_fetch("""
        SELECT 
            id, 
            user_id, 
            username, 
            contact_info, 
            created_at 
        FROM successful_dialogs 
        ORDER BY created_at DESC
    """)
    
    dialogs = []
    for dialog_id, user_id, username, contact_info_json, created_at in dialogs_data:
        contact_info = json.loads(contact_info_json) if contact_info_json else {}
        dialogs.append({
            "id": dialog_id,
            "user_id": user_id,
            "username": username or "Неизвестный",
            "contact_info": contact_info,
            "created_at": datetime.fromisoformat(created_at) if created_at else datetime.now()
        })
    
    # Проверяем, является ли запрос AJAX-запросом
    is_ajax = request.query_params.get("ajax", "").lower() == "true"
    
    # Если это AJAX-запрос, возвращаем только HTML-содержимое без базового шаблона
    if is_ajax:
        return templates.TemplateResponse(
            "successful_dialogs.html", 
            {"request": request, "dialogs": dialogs, "is_ajax": True}
        )
    
    return templates.TemplateResponse(
        "successful_dialogs.html", 
        {"request": request, "dialogs": dialogs, "is_ajax": False}
    )
