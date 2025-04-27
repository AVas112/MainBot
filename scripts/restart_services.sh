#!/bin/bash

# Скрипт для перезапуска сервисов telegrambot и botadmin
echo "Перезапуск сервисов..."

# Перезапуск telegrambot
echo "Перезапуск telegrambot.service"
systemctl restart telegrambot.service

# Перезапуск botadmin
echo "Перезапуск botadmin.service"
systemctl restart botadmin.service

# Проверка статуса после перезапуска
echo "
Проверка статуса после перезапуска:"

echo "
Статус telegrambot.service:"
systemctl status telegrambot.service --no-pager

echo "
Статус botadmin.service:"
systemctl status botadmin.service --no-pager

echo "
Перезапуск сервисов завершен."
