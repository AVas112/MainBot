#!/bin/bash

# Скрипт для управления сервисами telegrambot и botadmin

show_menu() {
    echo "===== Управление сервисами telegrambot и botadmin ====="
    echo "1. Запустить сервисы"
    echo "2. Проверить статус сервисов"
    echo "3. Включить автозапуск сервисов"
    echo "4. Перезапустить сервисы"
    echo "5. Остановить сервисы"
    echo "0. Выход"
    echo "Введите номер действия: "
}

start_services() {
    echo "Запуск сервисов..."
    systemctl start telegrambot.service
    systemctl start botadmin.service
    echo "Сервисы запущены."
}

check_status() {
    echo "Проверка статуса сервисов..."
    echo "
Статус telegrambot.service:"
    systemctl status telegrambot.service --no-pager
    echo "
Статус botadmin.service:"
    systemctl status botadmin.service --no-pager
}

enable_autostart() {
    echo "Включение автозапуска сервисов..."
    systemctl enable telegrambot.service
    systemctl enable botadmin.service
    echo "Автозапуск включен для обоих сервисов."
}

restart_services() {
    echo "Перезапуск сервисов..."
    systemctl restart telegrambot.service
    systemctl restart botadmin.service
    echo "Сервисы перезапущены."
}

stop_services() {
    echo "Остановка сервисов..."
    systemctl stop telegrambot.service
    systemctl stop botadmin.service
    echo "Сервисы остановлены."
}

# Обработка аргументов командной строки
if [ $# -gt 0 ]; then
    case $1 in
        start)
            start_services
            ;;
        status)
            check_status
            ;;
        enable)
            enable_autostart
            ;;
        restart)
            restart_services
            ;;
        stop)
            stop_services
            ;;
        *)
            echo "Неизвестный аргумент: $1"
            echo "Доступные аргументы: start, status, enable, restart, stop"
            exit 1
            ;;
    esac
    exit 0
fi

# Основной цикл программы (интерактивный режим)
while true; do
    show_menu
    read -r choice
    
    case $choice in
        1) start_services; echo "
"; ;;
        2) check_status; echo "
"; ;;
        3) enable_autostart; echo "
"; ;;
        4) restart_services; echo "
"; ;;
        5) stop_services; echo "
"; ;;
        0) echo "Выход из программы."; exit 0; ;;
        *) echo "Неверный выбор. Пожалуйста, выберите снова."; echo "
"; ;;
    esac
done
