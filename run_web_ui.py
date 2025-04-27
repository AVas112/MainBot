import os
import sys

# Добавляем текущую директорию в путь импорта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Импортируем и запускаем веб-интерфейс
from src.web_ui_main import main

if __name__ == "__main__":
    main()
