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
