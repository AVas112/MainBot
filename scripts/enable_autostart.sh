#!/bin/bash

# Скрипт для включения автозапуска сервисов telegrambot и botadmin
echo "Включение автозапуска для сервисов..."

# Включение автозапуска для telegrambot
systemctl enable telegrambot.service
echo "Автозапуск включен для telegrambot.service"

# Включение автозапуска для botadmin
systemctl enable botadmin.service
echo "Автозапуск включен для botadmin.service"

echo "
Настройка автозапуска завершена."
