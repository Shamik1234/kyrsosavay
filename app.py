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
        from database import Project, User
        projects = Project.query.filter_by(status='active').order_by(Project.created_at.desc()).limit(6).all()
        stats = {
            'projects': Project.query.count(),
            'users': User.query.count(),
            'universities': db.session.query(User.university).distinct().count()
        }
        return render_template('index.html', projects=projects, stats=stats, current_user=current_user)

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
        projects_list = Project.query.filter_by(status='active').order_by(Project.created_at.desc()).all()
        return render_template('projects.html', projects=projects_list, current_user=current_user)

    @app.route('/project/<int:project_id>')
    def project_detail(project_id):
        from database import Project, Application
        project = Project.query.get_or_404(project_id)

        # Парсим needed_roles
        needed_roles = []
        if project.needed_roles:
            for line in project.needed_roles.split('\n'):
                if ':' in line:
                    role, level = line.split(':', 1)
                    needed_roles.append({'role': role.strip(), 'level': level.strip()})

        # Проверяем, подал ли пользователь заявку
        has_applied = False
        if current_user.is_authenticated:
            has_applied = Application.query.filter_by(
                project_id=project_id,
                user_id=current_user.id
            ).first()

        return render_template('project_detail.html',
                               project=project,
                               needed_roles=needed_roles,
                               has_applied=has_applied,
                               current_user=current_user)

    @app.route('/create_project', methods=['GET', 'POST'])
    @login_required
    def create_project():
        from forms import ProjectForm

        form = ProjectForm()
        if form.validate_on_submit():
            project = Project(
                title=form.title.data,
                description=form.description.data,
                category=form.category.data,
                needed_roles=form.needed_roles.data,
                difficulty=form.difficulty.data,
                location_type=form.location_type.data,
                university_filter=form.university_filter.data or current_user.university,
                faculty_filter=form.faculty_filter.data,
                estimated_duration=form.estimated_duration.data,
                creator_id=current_user.id
            )

            db.session.add(project)
            db.session.commit()

            flash('Проект успешно создан!', 'success')
            return redirect(url_for('project_detail', project_id=project.id))

        return render_template('create_project.html', form=form)

    @app.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_project(project_id):
        from database import Project
        from forms import ProjectForm

        project = Project.query.get_or_404(project_id)

        # Проверяем, что текущий пользователь - создатель проекта
        if project.creator_id != current_user.id:
            flash('У вас нет прав редактировать этот проект', 'danger')
            return redirect(url_for('project_detail', project_id=project_id))

        form = ProjectForm()

        if form.validate_on_submit():
            project.title = form.title.data
            project.description = form.description.data
            project.category = form.category.data
            project.needed_roles = form.needed_roles.data
            project.difficulty = form.difficulty.data
            project.location_type = form.location_type.data
            project.university_filter = form.university_filter.data
            project.faculty_filter = form.faculty_filter.data
            project.estimated_duration = form.estimated_duration.data

            db.session.commit()
            flash('Проект успешно обновлен!', 'success')
            return redirect(url_for('project_detail', project_id=project.id))

        # Заполняем форму текущими данными
        if request.method == 'GET':
            form.title.data = project.title
            form.description.data = project.description
            form.category.data = project.category
            form.needed_roles.data = project.needed_roles
            form.difficulty.data = project.difficulty
            form.location_type.data = project.location_type
            form.university_filter.data = project.university_filter
            form.faculty_filter.data = project.faculty_filter
            form.estimated_duration.data = project.estimated_duration

        return render_template('edit_project.html', form=form, project=project)

    @app.route('/project/<int:project_id>/delete', methods=['POST'])
    @login_required
    def delete_project(project_id):
        from database import Project, Application

        project = Project.query.get_or_404(project_id)

        # Проверяем, что текущий пользователь - создатель проекта
        if project.creator_id != current_user.id:
            flash('У вас нет прав удалить этот проект', 'danger')
            return redirect(url_for('index'))

        # Удаляем все связанные заявки
        Application.query.filter_by(project_id=project_id).delete()

        # Удаляем проект
        db.session.delete(project)
        db.session.commit()

        flash('Проект успешно удален', 'success')
        return redirect(url_for('profile'))

    # ---------- ЗАЯВКИ ----------

    @app.route('/project/<int:project_id>/apply', methods=['POST'])
    @login_required
    def apply_to_project(project_id):
        from database import Project, Application

        project = Project.query.get_or_404(project_id)

        # Нельзя подавать заявку на свой проект
        if project.creator_id == current_user.id:
            flash('Вы не можете подать заявку на свой проект', 'warning')
            return redirect(url_for('project_detail', project_id=project_id))

        # Проверяем, не подал ли уже заявку
        existing = Application.query.filter_by(
            project_id=project_id,
            user_id=current_user.id
        ).first()

        if existing:
            flash('Вы уже подали заявку на этот проект', 'warning')
            return redirect(url_for('project_detail', project_id=project_id))

        role = request.form.get('role')
        message = request.form.get('message')

        application = Application(
            project_id=project_id,
            user_id=current_user.id,
            applied_role=role,
            message=message
        )

        db.session.add(application)
        db.session.commit()

        flash('Заявка успешно отправлена!', 'success')
        return redirect(url_for('project_detail', project_id=project_id))

    @app.route('/application/<int:app_id>/cancel', methods=['POST'])
    @login_required
    def cancel_application(app_id):
        from database import Application

        application = Application.query.get_or_404(app_id)

        # Проверяем, что текущий пользователь - автор заявки
        if application.user_id != current_user.id:
            flash('У вас нет прав отменить эту заявку', 'danger')
            return redirect(url_for('profile'))

        db.session.delete(application)
        db.session.commit()

        flash('Заявка успешно отменена', 'success')
        return redirect(url_for('profile'))
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

    # ---------- СОЗДАНИЕ ПРОЕКТА ----------

    @app.route('/create_project', methods=['GET', 'POST'])
    @login_required
    def create_project():
        from forms import ProjectForm  # Импортируем тут

        form = ProjectForm()
        if form.validate_on_submit():
            project = Project(
                title=form.title.data,
                description=form.description.data,
                category=form.category.data,
                needed_roles=form.needed_roles.data,
                difficulty=form.difficulty.data,
                location_type=form.location_type.data,
                university_filter=form.university_filter.data or current_user.university,
                faculty_filter=form.faculty_filter.data,
                estimated_duration=form.estimated_duration.data,
                creator_id=current_user.id
            )

            db.session.add(project)
            db.session.commit()

            flash('Проект успешно создан!', 'success')
            return redirect(url_for('project_detail', project_id=project.id))

        return render_template('create_project.html', form=form)
    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)