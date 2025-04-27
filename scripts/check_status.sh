#!/bin/bash

# Скрипт для проверки статуса сервисов telegrambot и botadmin
echo "Проверка статуса сервисов..."

# Проверка статуса telegrambot
echo "Статус telegrambot.service:"
systemctl status telegrambot.service --no-pager

# Проверка статуса botadmin
echo "
Статус botadmin.service:"
systemctl status botadmin.service --no-pager

echo "
Проверка статуса завершена."
