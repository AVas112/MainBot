#!/bin/bash

# Скрипт для запуска сервисов telegrambot и botadmin
echo "Запуск сервисов telegrambot и botadmin..."

# Запуск сервисов
systemctl start telegrambot.service
systemctl start botadmin.service

# Проверка статуса
echo "
Проверка статуса сервисов:
"
systemctl status telegrambot.service --no-pager
echo "
"
systemctl status botadmin.service --no-pager

echo "
Сервисы запущены."
