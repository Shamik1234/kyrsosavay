from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

db = SQLAlchemy()
login_manager = LoginManager()


# Модели ДО создания приложения
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100))
    university = db.Column(db.String(200))
    faculty = db.Column(db.String(200))
    course = db.Column(db.Integer)
    skills = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100))
    status = db.Column(db.String(50), default='active')
    needed_roles = db.Column(db.Text)
    difficulty = db.Column(db.String(50))
    location_type = db.Column(db.String(50))
    university_filter = db.Column(db.String(200))
    faculty_filter = db.Column(db.String(200))
    estimated_duration = db.Column(db.String(100))
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creator = db.relationship('User', backref='projects')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text)
    applied_role = db.Column(db.String(100))
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='applications')
    project = db.relationship('Project', backref='applications')


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-me')

    # База данных
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

    # Базовые маршруты
    @app.route('/')
    def index():
        projects = Project.query.filter_by(status='active').order_by(Project.created_at.desc()).limit(6).all()
        stats = {
            'projects': Project.query.count(),
            'users': User.query.count(),
            'universities': db.session.query(User.university).distinct().count() if User.query.count() > 0 else 0
        }
        return render_template('index.html', projects=projects, stats=stats)

    @app.route('/health')
    def health():
        return jsonify({'status': 'healthy'}), 200

    @app.route('/test-db')
    def test_db():
        try:
            user_count = User.query.count()
            project_count = Project.query.count()
            return jsonify({
                'status': 'DB работает',
                'users': user_count,
                'projects': project_count
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # Создаем таблицы при запуске
    with app.app_context():
        db.create_all()
        # Создаем тестового пользователя если нет пользователей
        if User.query.count() == 0:
            test_user = User(
                username='test',
                email='test@example.com',
                password_hash=generate_password_hash('password123'),
                full_name='Тестовый Пользователь',
                university='Тестовый Университет',
                faculty='Тестовый Факультет',
                course=3
            )
            db.session.add(test_user)
            db.session.commit()

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)