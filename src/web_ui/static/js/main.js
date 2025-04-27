// Основной JavaScript файл для веб-интерфейса

// Добавление активного класса для текущего пункта меню
document.addEventListener('DOMContentLoaded', function() {
    // Получаем текущий путь
    const currentPath = window.location.pathname;
    
    // Находим все ссылки в навигации
    const navLinks = document.querySelectorAll('.nav-link');
    
    // Добавляем активный класс для соответствующей ссылки
    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        
        if (currentPath === href || 
            (href !== '/admin/' && currentPath.startsWith(href))) {
            link.classList.add('active');
        }
    });
    
    // Добавляем обработчики событий для таблиц
    const tables = document.querySelectorAll('.table');
    tables.forEach(table => {
        if (table.classList.contains('table-hover')) {
            const rows = table.querySelectorAll('tbody tr');
            rows.forEach(row => {
                row.addEventListener('click', function(e) {
                    // Игнорируем клики по кнопкам
                    if (e.target.tagName.toLowerCase() !== 'button' && 
                        e.target.tagName.toLowerCase() !== 'a' && 
                        !e.target.closest('button') && 
                        !e.target.closest('a')) {
                        // Находим ссылку в этой строке
                        const link = row.querySelector('a');
                        if (link) {
                            window.location.href = link.getAttribute('href');
                        }
                    }
                });
            });
        }
    });
    
    // Инициализация автообновления страницы
    initAutoRefresh();
});

// Функция для форматирования даты и времени
function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// Функция для инициализации автообновления страницы
function initAutoRefresh() {
    // Проверяем, нужно ли включать автообновление для текущей страницы
    const currentPath = window.location.pathname;
    
    // Настройки автообновления
    const refreshInterval = 30000; // 30 секунд - оптимальное время обновления
    let refreshTimer = null;
    let isAutoRefreshEnabled = true;
    
    // Создаем и добавляем переключатель автообновления в навигационную панель
    const navbarNav = document.querySelector('#navbarNav');
    if (navbarNav) {
        const autoRefreshToggle = document.createElement('div');
        autoRefreshToggle.className = 'ms-auto d-flex align-items-center';
        autoRefreshToggle.innerHTML = `
            <div class="form-check form-switch">
                <input class="form-check-input" type="checkbox" id="autoRefreshToggle" checked>
                <label class="form-check-label text-light" for="autoRefreshToggle">Автообновление</label>
            </div>
            <div id="refreshCountdown" class="ms-2 text-light"></div>
        `;
        navbarNav.appendChild(autoRefreshToggle);
        
        // Добавляем обработчик события для переключателя
        const toggleCheckbox = document.getElementById('autoRefreshToggle');
        if (toggleCheckbox) {
            toggleCheckbox.addEventListener('change', function() {
                isAutoRefreshEnabled = this.checked;
                if (isAutoRefreshEnabled) {
                    startRefreshTimer();
                } else {
                    clearTimeout(refreshTimer);
                    const countdownElement = document.getElementById('refreshCountdown');
                    if (countdownElement) {
                        countdownElement.textContent = '';
                    }
                }
            });
        }
    }
    
    // Функция для обновления данных на странице
    function refreshPageData() {
        // Определяем, какие данные нужно обновить в зависимости от текущей страницы
        if (currentPath === '/admin/' || currentPath === '/admin') {
            // Обновление списка пользователей
            fetch('/admin/?ajax=true')
                .then(response => response.text())
                .then(html => {
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    
                    // Обновляем таблицу пользователей
                    const newTable = doc.querySelector('.card:first-child .table-responsive');
                    const currentTable = document.querySelector('.card:first-child .table-responsive');
                    if (newTable && currentTable) {
                        currentTable.innerHTML = newTable.innerHTML;
                    }
                    
                    // Обновляем таблицу успешных диалогов, если она есть
                    const newSuccessTable = doc.querySelector('.card:last-child .table-responsive');
                    const currentSuccessTable = document.querySelector('.card:last-child .table-responsive');
                    if (newSuccessTable && currentSuccessTable) {
                        currentSuccessTable.innerHTML = newSuccessTable.innerHTML;
                    }
                    
                    // Перепривязываем обработчики событий к новым строкам таблицы
                    const tables = document.querySelectorAll('.table');
                    tables.forEach(table => {
                        if (table.classList.contains('table-hover')) {
                            const rows = table.querySelectorAll('tbody tr');
                            rows.forEach(row => {
                                row.addEventListener('click', function(e) {
                                    if (e.target.tagName.toLowerCase() !== 'button' && 
                                        e.target.tagName.toLowerCase() !== 'a' && 
                                        !e.target.closest('button') && 
                                        !e.target.closest('a')) {
                                        const link = row.querySelector('a');
                                        if (link) {
                                            window.location.href = link.getAttribute('href');
                                        }
                                    }
                                });
                            });
                        }
                    });
                })
                .catch(error => console.error('Ошибка при обновлении данных:', error));
        } else if (currentPath.includes('/admin/dialog/')) {
            // Обновление диалога с пользователем
            fetch(currentPath + '?ajax=true')
                .then(response => response.text())
                .then(html => {
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    
                    // Обновляем содержимое диалога
                    const newDialogContent = doc.querySelector('.card-body');
                    const currentDialogContent = document.querySelector('.card-body');
                    if (newDialogContent && currentDialogContent) {
                        currentDialogContent.innerHTML = newDialogContent.innerHTML;
                    }
                })
                .catch(error => console.error('Ошибка при обновлении диалога:', error));
        } else if (currentPath.includes('/admin/successful_dialogs')) {
            // Обновление списка успешных диалогов
            fetch('/admin/successful_dialogs?ajax=true')
                .then(response => response.text())
                .then(html => {
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    
                    // Обновляем таблицу успешных диалогов
                    const newTable = doc.querySelector('.table-responsive');
                    const currentTable = document.querySelector('.table-responsive');
                    if (newTable && currentTable) {
                        currentTable.innerHTML = newTable.innerHTML;
                    }
                    
                    // Перепривязываем обработчики событий к новым строкам таблицы
                    const table = document.querySelector('.table');
                    if (table && table.classList.contains('table-hover')) {
                        const rows = table.querySelectorAll('tbody tr');
                        rows.forEach(row => {
                            row.addEventListener('click', function(e) {
                                if (e.target.tagName.toLowerCase() !== 'button' && 
                                    e.target.tagName.toLowerCase() !== 'a' && 
                                    !e.target.closest('button') && 
                                    !e.target.closest('a')) {
                                    const link = row.querySelector('a');
                                    if (link) {
                                        window.location.href = link.getAttribute('href');
                                    }
                                }
                            });
                        });
                    }
                })
                .catch(error => console.error('Ошибка при обновлении успешных диалогов:', error));
        }
        
        // Запускаем таймер для следующего обновления
        if (isAutoRefreshEnabled) {
            startRefreshTimer();
        }
    }
    
    // Функция для запуска таймера обновления с обратным отсчетом
    function startRefreshTimer() {
        let timeLeft = refreshInterval / 1000;
        const countdownElement = document.getElementById('refreshCountdown');
        
        // Обновляем счетчик каждую секунду
        function updateCountdown() {
            if (countdownElement) {
                countdownElement.textContent = `(${timeLeft}с)`;
            }
            
            timeLeft -= 1;
            
            if (timeLeft > 0) {
                setTimeout(updateCountdown, 1000);
            }
        }
        
        // Запускаем обратный отсчет
        updateCountdown();
        
        // Запускаем таймер обновления
        refreshTimer = setTimeout(refreshPageData, refreshInterval);
    }
    
    // Запускаем автообновление, если включено
    if (isAutoRefreshEnabled) {
        startRefreshTimer();
    }
    
    // Останавливаем обновление, когда страница не активна
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            // Страница не активна, останавливаем обновление
            clearTimeout(refreshTimer);
        } else if (isAutoRefreshEnabled) {
            // Страница снова активна, возобновляем обновление
            startRefreshTimer();
        }
    });
}
