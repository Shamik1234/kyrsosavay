// Базовый скрипт для Colab Hub
document.addEventListener('DOMContentLoaded', function() {
    console.log('Colab Hub запущен!');

    // Автоматическое скрытие алертов через 5 секунд
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Подтверждение действий
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            const message = this.getAttribute('data-confirm');
            if (!confirm(message || 'Вы уверены?')) {
                e.preventDefault();
            }
        });
    });
});