from flask import Flask, render_template, jsonify
import os
from database import db, login_manager, User
from werkzeug.security import generate_password_hash


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

    # Настройка базы данных
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///colab_hub.db'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Инициализация
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Маршруты
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/health')
    def health():
        return jsonify({'status': 'healthy'}), 200

    @app.route('/test-db')
    def test_db():
        try:
            user_count = User.query.count()
            return jsonify({
                'status': 'База данных работает',
                'users': user_count,
                'message': 'Colab Hub готов к работе!'
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # Создаем таблицы и тестового пользователя
    with app.app_context():
        db.create_all()
        # Создаем тестового пользователя если база пустая
        if User.query.count() == 0:
            test_user = User(
                username='testuser',
                email='test@example.com',
                password_hash=generate_password_hash('password123'),
                full_name='Тестовый Пользователь',
                university='МГУ',
                faculty='Факультет информатики',
                course=3,
                skills='Python, Flask, SQL'
            )
            db.session.add(test_user)
            db.session.commit()

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)