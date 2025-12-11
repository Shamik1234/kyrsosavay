import os
from flask import Flask
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


def create_app():
    app = Flask(__name__)

    # Конфигурация
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-me')

    # База данных для Render
    if os.environ.get('DATABASE_URL'):
        database_url = os.environ['DATABASE_URL']
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///colab_hub.db'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Инициализация расширений
    from models import db
    db.init_app(app)

    from flask_login import LoginManager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.query.get(int(user_id))

    # Регистрация маршрутов
    from routes import init_routes
    init_routes(app)

    return app


# Создаем экземпляр приложения
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)