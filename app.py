from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
import os
from database import db, login_manager, User
from werkzeug.security import generate_password_hash, check_password_hash
from forms import LoginForm, RegisterForm


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

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

    # ========== МАРШРУТЫ ==========

    @app.route('/')
    def index():
        return render_template('index.html', current_user=current_user)

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

    # ---------- АВТОРИЗАЦИЯ ----------

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()
            if user and check_password_hash(user.password_hash, form.password.data):
                login_user(user, remember=True)
                flash('Вы успешно вошли в систему!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Неверный email или пароль', 'danger')

        return render_template('login.html', form=form)

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        form = RegisterForm()
        if form.validate_on_submit():
            # Проверяем, нет ли уже такого пользователя
            existing_user = User.query.filter(
                (User.email == form.email.data) | (User.username == form.username.data)
            ).first()

            if existing_user:
                flash('Пользователь с таким email или логином уже существует', 'danger')
                return redirect(url_for('register'))

            # Создаем нового пользователя
            user = User(
                username=form.username.data,
                email=form.email.data,
                password_hash=generate_password_hash(form.password.data),
                full_name=form.full_name.data,
                university=form.university.data,
                faculty=form.faculty.data,
                course=int(form.course.data),
                skills=form.skills.data
            )

            db.session.add(user)
            db.session.commit()

            flash('Регистрация успешна! Теперь войдите в систему.', 'success')
            return redirect(url_for('login'))

        return render_template('register.html', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('Вы вышли из системы', 'info')
        return redirect(url_for('index'))

    @app.route('/profile')
    @login_required
    def profile():
        return render_template('profile.html', user=current_user)

    # ---------- ПРОЕКТЫ ----------

    @app.route('/projects')
    def projects():
        from database import Project
        projects = Project.query.filter_by(status='active').order_by(Project.created_at.desc()).all()
        return render_template('projects.html', projects=projects, current_user=current_user)

    # Создаем таблицы при запуске
    with app.app_context():
        # Импортируем здесь чтобы избежать циклических импортов
        from database import Project, Application
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

            # Создаем тестовый проект
            test_project = Project(
                title='Тестовый проект: Разработка платформы',
                description='Разрабатываем платформу для студенческих проектов',
                category='it',
                difficulty='intermediate',
                location_type='online',
                university_filter='МГУ',
                faculty_filter='Факультет информатики',
                estimated_duration='3 месяца',
                needed_roles='backend:middle\nfrontend:beginner\ndesigner:any',
                creator_id=1
            )
            db.session.add(test_project)

            db.session.commit()

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)