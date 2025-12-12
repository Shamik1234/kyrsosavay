# reset_db.py
from app import app, db
import sys

print("🔄 Начинаю сброс базы данных...")

with app.app_context():
    try:
        # Удаляем все таблицы
        db.drop_all()
        print("✅ Все таблицы удалены")

        # Создаем заново
        db.create_all()
        print("✅ Все таблицы созданы заново")
        print("📊 Созданные таблицы:")
        print("   - User (пользователи)")
        print("   - Project (проекты)")
        print("   - Application (заявки)")
        print("   - Message (сообщения чата)")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)