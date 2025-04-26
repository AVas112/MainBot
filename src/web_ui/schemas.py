from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel


class Message(BaseModel):
    """Модель сообщения диалога.
    
    Parameters
    ----------
    message : str
        Текст сообщения
    role : str
        Роль отправителя (user/assistant)
    timestamp : datetime
        Время отправки сообщения
    """
    message: str
    role: str
    timestamp: datetime


class Dialog(BaseModel):
    """Модель диалога с пользователем.
    
    Parameters
    ----------
    user_id : int
        ID пользователя
    username : str
        Имя пользователя
    messages : List[Message]
        Список сообщений диалога
    """
    user_id: int
    username: str
    messages: List[Message]


class User(BaseModel):
    """Модель пользователя.
    
    Parameters
    ----------
    user_id : int
        ID пользователя
    username : str
        Имя пользователя
    last_message : datetime
        Время последнего сообщения
    message_count : int
        Количество сообщений
    """
    user_id: int
    username: str
    last_message: datetime
    message_count: int


class SuccessfulDialog(BaseModel):
    """Модель успешного диалога.
    
    Parameters
    ----------
    id : int
        ID записи
    user_id : int
        ID пользователя
    username : str
        Имя пользователя
    contact_info : Dict[str, Any]
        Контактная информация пользователя
    messages : List[Dict[str, Any]]
        Список сообщений диалога
    created_at : datetime
        Время создания записи
    """
    id: int
    user_id: int
    username: str
    contact_info: Dict[str, Any]
    messages: List[Dict[str, Any]]
    created_at: datetime
