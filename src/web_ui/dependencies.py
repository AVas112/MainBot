from typing import Annotated

from fastapi import Depends

# Возвращаем исходный импорт
from src.database import Database


async def get_database() -> Database:
    """Зависимость для получения экземпляра базы данных.
    
    Returns
    -------
    Database
        Экземпляр класса Database
    """
    db = Database()
    await db.init_db()
    return db


# Типизированная зависимость для использования в маршрутах
DatabaseDep = Annotated[Database, Depends(get_database)]
