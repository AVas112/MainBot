import os

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.web_ui.router import router


def create_app() -> FastAPI:
    """Создание экземпляра FastAPI приложения.
    
    Returns
    -------
    FastAPI
        Экземпляр FastAPI приложения
    """
    app = FastAPI(
        title="Telegram Bot Admin Panel",
        description="Административная панель для просмотра диалогов Telegram бота",
        version="1.0.0"
    )
    
    static_dir = os.path.join(os.path.dirname(__file__), "web_ui", "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    app.include_router(router)
    
    @app.get("/")
    async def redirect_to_admin():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/admin/")
    
    return app


def main():
    """Точка входа для запуска веб-интерфейса."""
    app = create_app()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


if __name__ == "__main__":
    main()
