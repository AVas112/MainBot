# Makefile для управления тестами проекта MainBot

.PHONY: help install test test-unit test-integration test-performance test-coverage test-fast test-slow clean lint format

# Показать справку
help:
	@echo "Доступные команды:"
	@echo "  install          - Установить зависимости"
	@echo "  test             - Запустить все тесты"
	@echo "  test-unit        - Запустить только юнит-тесты"
	@echo "  test-integration - Запустить интеграционные тесты"
	@echo "  test-performance - Запустить тесты производительности"
	@echo "  test-coverage    - Запустить тесты с покрытием кода"
	@echo "  test-fast        - Запустить быстрые тесты"
	@echo "  test-slow        - Запустить медленные тесты"
	@echo "  lint             - Проверить код линтером"
	@echo "  format           - Отформатировать код"
	@echo "  clean            - Очистить временные файлы"

# Установить зависимости
install:
	poetry install

# Запустить все тесты
test:
	poetry run pytest

# Запустить только юнит-тесты
test-unit:
	poetry run pytest tests/unit/ -m "unit or not integration"

# Запустить интеграционные тесты
test-integration:
	poetry run pytest tests/unit/test_chatgpt_assistant_integration.py -m "integration"

# Запустить тесты производительности
test-performance:
	poetry run pytest tests/unit/test_chatgpt_assistant_performance.py -m "slow"

# Запустить тесты с покрытием кода
test-coverage:
	poetry run pytest --cov=src --cov-report=html --cov-report=term-missing

# Запустить быстрые тесты
test-fast:
	poetry run pytest -m "not slow"

# Запустить медленные тесты
test-slow:
	poetry run pytest -m "slow"

# Проверить код линтером
lint:
	poetry run ruff check src/ tests/

# Отформатировать код
format:
	poetry run ruff format src/ tests/
	poetry run autoflake src/ tests/

# Очистить временные файлы
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage