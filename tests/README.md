# Тестирование проекта MainBot

Этот документ описывает структуру и подходы к тестированию проекта MainBot.

## Структура тестов

```
tests/
├── __init__.py                                    # Инициализация пакета тестов
├── conftest.py                                   # Общие фикстуры и конфигурация
├── README.md                                     # Документация по тестированию
└── unit/                                         # Юнит-тесты
    ├── __init__.py
    ├── test_chatgpt_assistant.py                # Основные юнит-тесты
    ├── test_chatgpt_assistant_integration.py    # Интеграционные тесты
    └── test_chatgpt_assistant_performance.py    # Тесты производительности
```

## Типы тестов

### 1. Юнит-тесты (`test_chatgpt_assistant.py`)
Тестируют отдельные методы и функции класса `ChatGPTAssistant`:
- Инициализация класса
- Создание тредов
- Добавление сообщений пользователя
- Создание и обработка run
- Получение ответов от ассистента
- Обработка требуемых действий
- Обработка контактной информации
- Отправка уведомлений

### 2. Интеграционные тесты (`test_chatgpt_assistant_integration.py`)
Тестируют взаимодействие между компонентами:
- Полный цикл разговора с получением контактной информации
- Обработка множественных повторных попыток
- Обработка сетевых ошибок
- Длительные процессы обработки
- Граничные случаи и обработка ошибок

### 3. Тесты производительности (`test_chatgpt_assistant_performance.py`)
Тестируют производительность и масштабируемость:
- Одновременные запросы
- Использование памяти при больших ответах
- Измерение времени ответа
- Стресс-тестирование
- Масштабируемость с множественными пользователями

## Используемые библиотеки

- **pytest** - основной фреймворк для тестирования
- **pytest-asyncio** - поддержка асинхронных тестов
- **pytest-mock** - мокирование объектов
- **pytest-cov** - измерение покрытия кода

## Запуск тестов

### Установка зависимостей
```bash
poetry install
```

### Запуск всех тестов
```bash
make test
# или
poetry run pytest
```

### Запуск конкретных типов тестов
```bash
# Только юнит-тесты
make test-unit

# Интеграционные тесты
make test-integration

# Тесты производительности
make test-performance

# Быстрые тесты (исключая медленные)
make test-fast

# Медленные тесты
make test-slow
```

### Запуск с покрытием кода
```bash
make test-coverage
# или
poetry run pytest --cov=src --cov-report=html --cov-report=term-missing
```

### Запуск конкретного теста
```bash
# Запуск конкретного файла
poetry run pytest tests/unit/test_chatgpt_assistant.py

# Запуск конкретного класса
poetry run pytest tests/unit/test_chatgpt_assistant.py::TestChatGPTAssistantInit

# Запуск конкретного метода
poetry run pytest tests/unit/test_chatgpt_assistant.py::TestChatGPTAssistantInit::test_init_without_telegram_bot
```

## Маркеры тестов

- `@pytest.mark.unit` - юнит-тесты
- `@pytest.mark.integration` - интеграционные тесты
- `@pytest.mark.slow` - медленные тесты (производительность, стресс-тесты)
- `@pytest.mark.asyncio` - асинхронные тесты

## Фикстуры

В файле `conftest.py` определены следующие фикстуры:

- `mock_config` - мок конфигурации приложения
- `mock_openai_client` - мок OpenAI клиента
- `mock_telegram_bot` - мок Telegram бота
- `mock_proxy_client` - мок прокси клиента
- `mock_email_service` - мок email сервиса
- `mock_notify_admin` - мок функции уведомления администратора
- `event_loop` - event loop для асинхронных тестов

## Принципы тестирования

### 1. Разделение ответственности
Каждый тест проверяет только одну функциональность или сценарий.

### 2. DRY (Don't Repeat Yourself)
Общие настройки и моки вынесены в фикстуры в `conftest.py`.

### 3. Изоляция тестов
Каждый тест независим и не влияет на другие тесты.

### 4. Мокирование внешних зависимостей
Все внешние API и сервисы мокируются для обеспечения стабильности тестов.

### 5. Покрытие граничных случаев
Тесты покрывают как успешные сценарии, так и обработку ошибок.

## Конфигурация pytest

Конфигурация находится в файле `pytest.ini`:

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --verbose
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=src
    --cov-report=term-missing
    --cov-report=html:htmlcov
    --cov-fail-under=80
asyncio_mode = auto
```

## Отчеты о покрытии

После запуска тестов с покрытием:
- Консольный отчет выводится в терминал
- HTML отчет сохраняется в папку `htmlcov/`
- Минимальное покрытие установлено на 80%

## Рекомендации по написанию тестов

### 1. Именование тестов
```python
def test_method_name_expected_behavior():
    """Описание того, что тестирует метод."""
```

### 2. Структура теста (AAA pattern)
```python
def test_example():
    # Arrange - подготовка данных
    mock_data = {"key": "value"}
    
    # Act - выполнение тестируемого кода
    result = function_under_test(mock_data)
    
    # Assert - проверка результатов
    assert result == expected_value
```

### 3. Использование моков
```python
@patch("module.external_dependency")
def test_with_mock(mock_dependency):
    mock_dependency.return_value = "mocked_value"
    # тест код
```

### 4. Асинхронные тесты
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result == expected_value
```

## Непрерывная интеграция

Тесты должны запускаться автоматически при каждом коммите. Рекомендуется настроить CI/CD пайплайн для:
- Запуска всех тестов
- Проверки покрытия кода
- Линтинга кода
- Генерации отчетов

## Отладка тестов

### Запуск с подробным выводом
```bash
poetry run pytest -v -s
```

### Запуск с отладочной информацией
```bash
poetry run pytest --pdb
```

### Запуск только упавших тестов
```bash
poetry run pytest --lf
```

## Поддержка и развитие

При добавлении новой функциональности в `ChatGPTAssistant`:
1. Добавьте соответствующие юнит-тесты
2. Обновите интеграционные тесты при необходимости
3. Добавьте тесты производительности для критичных функций
4. Обновите документацию

При обнаружении багов:
1. Сначала напишите тест, воспроизводящий баг
2. Исправьте код
3. Убедитесь, что тест проходит
4. Запустите все тесты для проверки регрессий