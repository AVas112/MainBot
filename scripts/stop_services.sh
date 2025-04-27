#!/bin/bash

# Скрипт для остановки сервисов telegrambot и botadmin
echo "Остановка сервисов..."

# Остановка telegrambot
systemctl stop telegrambot.service
echo "Остановлен telegrambot.service"

# Остановка botadmin
systemctl stop botadmin.service
echo "Остановлен botadmin.service"

# Проверка статуса после остановки
echo "
Проверка статуса после остановки:"

echo "
Статус telegrambot.service:"
systemctl status telegrambot.service --no-pager

echo "
Статус botadmin.service:"
systemctl status botadmin.service --no-pager

echo "
Сервисы остановлены."
