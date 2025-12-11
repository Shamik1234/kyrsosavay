from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
import os
from datetime import datetime
from database import db, login_manager, User, Project, Application
from werkzeug.security import generate_password_hash, check_password_hash
from forms import LoginForm, RegisterForm, ProjectForm, EditProfileForm

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

# Инициализация расширений
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ========== МАРШРУТЫ ==========

@app.route('/')
def index():
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

    # Диагностика
    if request.method == 'POST':
        print(f"=== ДАННЫЕ РЕГИСТРАЦИИ ===")
        print(f"Пароль: {request.form.get('password', 'НЕ ПЕРЕДАН')}")
        print(f"Подтверждение: {request.form.get('confirm_password', 'НЕ ПЕРЕДАН')}")
        print(f"Ошибки формы: {form.errors}")

    if form.validate_on_submit():
        existing_user = User.query.filter(
            (User.email == form.email.data) | (User.username == form.username.data)
        ).first()

        if existing_user:
            flash('Пользователь с таким email или логином уже существует', 'danger')
            return redirect(url_for('register'))

        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            full_name=form.full_name.data,
            university=form.university.data,
            faculty=form.faculty.data,
            course=int(form.course.data) if form.course.data and form.course.data.isdigit() else 1,
            skills=form.skills.data
        )

        db.session.add(user)
        db.session.commit()

        flash('Регистрация успешна! Теперь войдите в систему.', 'success')
        return redirect(url_for('login'))

    # Показываем ошибки валидации
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"Ошибка в поле '{field}': {error}", 'danger')

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
    user_projects = Project.query.filter_by(creator_id=current_user.id).all()
    applications = Application.query.filter_by(user_id=current_user.id).all()
    return render_template('profile.html',
                           user_projects=user_projects,
                           applications=applications,
                           current_user=current_user)


# ---------- СТРАНИЦА СТУДЕНТОВ ----------

@app.route('/students')
def students():
    search = request.args.get('search', '')
    university = request.args.get('university', '')
    skill_filter = request.args.get('skill', '')

    query = User.query

    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) |
            (User.full_name.ilike(f'%{search}%')) |
            (User.skills.ilike(f'%{search}%'))
        )

    if university and university != 'all':
        query = query.filter(User.university == university)

    if skill_filter:
        query = query.filter(User.skills.ilike(f'%{skill_filter}%'))

    students = query.order_by(User.created_at.desc()).all()

    # Получаем уникальные вузы для фильтра
    universities = db.session.query(User.university).distinct().all()

    # Собираем уникальные навыки
    all_skills = set()
    for student in User.query.all():
        if student.skills:
            for skill in student.skills.split(','):
                all_skills.add(skill.strip().lower())

    return render_template('students.html',
                           students=students,
                           universities=[u[0] for u in universities if u[0]],
                           skills=sorted(all_skills),
                           search_query=search,
                           current_user=current_user)


# ---------- ПРОЕКТЫ ----------

@app.route('/projects')
def projects():
    page = request.args.get('page', 1, type=int)
    per_page = 9

    projects_list = Project.query.filter_by(status='active') \
        .order_by(Project.created_at.desc()) \
        .paginate(page=page, per_page=per_page, error_out=False)

    return render_template('projects.html',
                           projects=projects_list,
                           current_user=current_user)


@app.route('/project/<int:project_id>')
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)

    # Парсим needed_roles в удобный формат для шаблона
    needed_roles = []
    if project.needed_roles:
        # Удаляем лишние пробелы и разбиваем по строкам
        lines = project.needed_roles.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if ':' in line:
                # Формат: "роль:уровень"
                parts = line.split(':', 1)
                role_name = parts[0].strip()
                level = parts[1].strip() if len(parts) > 1 else 'любой'
            else:
                # Формат: просто "роль"
                role_name = line
                level = 'любой'

            if role_name:  # Проверяем, что роль не пустая
                needed_roles.append({
                    'role': role_name,
                    'level': level,
                    'full': f"{role_name} ({level})"
                })

    # Если роли не распарсились, пробуем через запятую
    if not needed_roles and project.needed_roles:
        roles_list = [r.strip() for r in project.needed_roles.split(',') if r.strip()]
        for role_name in roles_list:
            needed_roles.append({
                'role': role_name,
                'level': 'любой',
                'full': role_name
            })

    # Проверяем, подал ли пользователь заявку
    has_applied = False
    application_id = None
    if current_user.is_authenticated:
        application = Application.query.filter_by(
            project_id=project_id,
            user_id=current_user.id
        ).first()
        if application:
            has_applied = True
            application_id = application.id

    return render_template('project_detail.html',
                           project=project,
                           needed_roles=needed_roles,
                           has_applied=has_applied,
                           application_id=application_id,
                           current_user=current_user)


@app.route('/create_project', methods=['GET', 'POST'])
@login_required
def create_project():
    form = ProjectForm()
    if form.validate_on_submit():
        # Обработка ролей из SelectMultipleField
        roles_list = form.needed_roles.data if hasattr(form.needed_roles, 'data') else []

        # Преобразуем список ролей в строку формата "роль:уровень\nроль:уровень"
        roles_text = ""
        if roles_list and isinstance(roles_list, list):
            for role in roles_list:
                # Если роль из предопределенного списка
                roles_text += f"{role}:средний\n"
        elif form.needed_roles.data:  # Если это текст из TextArea
            roles_text = form.needed_roles.data

        project = Project(
            title=form.title.data,
            description=form.description.data,
            category=form.category.data,
            needed_roles=roles_text,
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
    project = Project.query.get_or_404(project_id)

    # Проверяем, что текущий пользователь - создатель проекта
    if project.creator_id != current_user.id:
        flash('У вас нет прав редактировать этот проект', 'danger')
        return redirect(url_for('project_detail', project_id=project_id))

    form = ProjectForm()

    if form.validate_on_submit():
        # Обработка ролей
        roles_list = form.needed_roles.data if hasattr(form.needed_roles, 'data') else []
        roles_text = ""
        if roles_list and isinstance(roles_list, list):
            for role in roles_list:
                roles_text += f"{role}:средний\n"
        elif form.needed_roles.data:
            roles_text = form.needed_roles.data

        project.title = form.title.data
        project.description = form.description.data
        project.category = form.category.data
        project.needed_roles = roles_text
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

    role = request.form.get('role', '').strip()
    message = request.form.get('message', '').strip()

    # ВАЖНО: Проверяем, что роль и сообщение заполнены
    if not role:
        flash('Пожалуйста, выберите роль', 'danger')
        return redirect(url_for('project_detail', project_id=project_id))

    if not message:
        flash('Пожалуйста, напишите сообщение', 'danger')
        return redirect(url_for('project_detail', project_id=project_id))

    if len(message) < 10:
        flash('Сообщение слишком короткое (минимум 10 символов)', 'danger')
        return redirect(url_for('project_detail', project_id=project_id))

    # Парсим роли проекта для проверки
    valid_roles = []
    if project.needed_roles:
        lines = project.needed_roles.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            if ':' in line:
                # Берем только часть до двоеточия (название роли)
                valid_role = line.split(':')[0].strip()
                valid_roles.append(valid_role)
            else:
                valid_roles.append(line.strip())

    # Если роли не распарсились через переносы, пробуем через запятую
    if not valid_roles and project.needed_roles:
        valid_roles = [r.strip() for r in project.needed_roles.split(',') if r.strip()]

    # Проверяем, что выбранная роль есть в списке допустимых
    if valid_roles and role not in valid_roles:
        flash(f'Роль "{role}" не найдена в списке требуемых ролей для этого проекта', 'danger')
        return redirect(url_for('project_detail', project_id=project_id))

    application = Application(
        project_id=project_id,
        user_id=current_user.id,
        applied_role=role,
        message=message
    )

    db.session.add(application)
    db.session.commit()

    flash('Заявка успешно отправлена! Ожидайте ответа от автора проекта.', 'success')
    return redirect(url_for('project_detail', project_id=project_id))


@app.route('/application/<int:app_id>/cancel', methods=['POST'])
@login_required
def cancel_application(app_id):
    application = Application.query.get_or_404(app_id)

    # Проверяем, что текущий пользователь - автор заявки
    if application.user_id != current_user.id:
        flash('У вас нет прав отменить эту заявку', 'danger')
        return redirect(url_for('profile'))

    db.session.delete(application)
    db.session.commit()

    flash('Заявка успешно отменена', 'success')
    return redirect(url_for('profile'))


@app.route('/project/<int:project_id>/applications')
@login_required
def project_applications(project_id):
    project = Project.query.get_or_404(project_id)

    # Проверяем, что текущий пользователь - создатель проекта
    if project.creator_id != current_user.id:
        flash('У вас нет прав просматривать заявки на этот проект', 'danger')
        return redirect(url_for('project_detail', project_id=project_id))

    applications = Application.query.filter_by(project_id=project_id).all()
    return render_template('project_applications.html',
                           project=project,
                           applications=applications,
                           current_user=current_user)


@app.route('/application/<int:app_id>/<action>')
@login_required
def handle_application(app_id, action):
    application = Application.query.get_or_404(app_id)
    project = Project.query.get_or_404(application.project_id)

    # Проверяем, что текущий пользователь - создатель проекта
    if project.creator_id != current_user.id:
        flash('У вас нет прав для этого действия', 'danger')
        return redirect(url_for('project_detail', project_id=project.id))

    if action == 'accept':
        application.status = 'accepted'
        flash(f'Заявка от {application.user.username} принята!', 'success')
    elif action == 'reject':
        application.status = 'rejected'
        flash(f'Заявка от {application.user.username} отклонена', 'info')
    else:
        flash('Неизвестное действие', 'danger')

    db.session.commit()
    return redirect(url_for('project_applications', project_id=project.id))


# ---------- РЕДАКТИРОВАНИЕ ПРОФИЛЯ ----------

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()

    if form.validate_on_submit():
        current_user.full_name = form.full_name.data
        current_user.university = form.university.data
        current_user.faculty = form.faculty.data

        # Безопасное преобразование курса
        if form.course.data and form.course.data.isdigit():
            current_user.course = int(form.course.data)
        else:
            current_user.course = 1

        current_user.skills = form.skills.data
        current_user.bio = form.bio.data if hasattr(form, 'bio') else None

        db.session.commit()
        flash('Профиль успешно обновлен!', 'success')
        return redirect(url_for('profile'))

    # Заполняем форму текущими данными
    if request.method == 'GET':
        form.full_name.data = current_user.full_name or ''
        form.university.data = current_user.university or ''
        form.faculty.data = current_user.faculty or ''
        form.course.data = str(current_user.course) if current_user.course else '1'
        form.skills.data = current_user.skills or ''
        if hasattr(form, 'bio') and hasattr(current_user, 'bio'):
            form.bio.data = current_user.bio or ''

    return render_template('edit_profile.html', form=form)


# ---------- ПОИСК И ФИЛЬТРАЦИЯ ----------

@app.route('/search')
def search_projects():
    query = request.args.get('q', '')
    category = request.args.get('category', '')
    university = request.args.get('university', '')
    difficulty = request.args.get('difficulty', '')

    # Базовый запрос
    projects_query = Project.query.filter_by(status='active')

    # Применяем фильтры
    if query:
        projects_query = projects_query.filter(
            (Project.title.ilike(f'%{query}%')) |
            (Project.description.ilike(f'%{query}%'))
        )

    if category and category != 'all':
        projects_query = projects_query.filter_by(category=category)

    if university and university != 'all':
        projects_query = projects_query.filter_by(university_filter=university)

    if difficulty and difficulty != 'all':
        projects_query = projects_query.filter_by(difficulty=difficulty)

    projects = projects_query.order_by(Project.created_at.desc()).all()

    # Получаем уникальные значения для фильтров
    categories = db.session.query(Project.category).distinct().all()
    universities = db.session.query(Project.university_filter).distinct().all()
    difficulties = ['beginner', 'intermediate', 'advanced']

    return render_template('search.html',
                           projects=projects,
                           search_query=query,
                           categories=[c[0] for c in categories if c[0]],
                           universities=[u[0] for u in universities if u[0]],
                           difficulties=difficulties,
                           selected_category=category,
                           selected_university=university,
                           selected_difficulty=difficulty,
                           current_user=current_user)


# ---------- ЧАТЫ (базовая версия) ----------

@app.route('/chats')
@login_required
def chats():
    # Получаем все заявки пользователя, где есть общение
    user_applications = Application.query.filter_by(user_id=current_user.id).all()

    # Получаем все проекты пользователя, где есть заявки
    user_projects = Project.query.filter_by(creator_id=current_user.id).all()

    # Собираем все чаты (заявки)
    all_chats = []

    # Чат как соискатель
    for app in user_applications:
        if app.project:
            all_chats.append({
                'id': app.id,
                'type': 'applicant',
                'project': app.project,
                'application': app,
                'last_message_time': app.created_at,
                'unread': False
            })

    # Чат как создатель проекта
    for project in user_projects:
        applications = Application.query.filter_by(project_id=project.id).all()
        for app in applications:
            all_chats.append({
                'id': app.id,
                'type': 'creator',
                'project': project,
                'application': app,
                'user': app.user,
                'last_message_time': app.created_at,
                'unread': False
            })

    # Сортируем по времени
    all_chats.sort(key=lambda x: x['last_message_time'], reverse=True)

    return render_template('chats.html',
                           chats=all_chats,
                           current_user=current_user)


@app.route('/chat/<int:application_id>')
@login_required
def chat(application_id):
    application = Application.query.get_or_404(application_id)

    # Проверяем доступ
    if application.user_id != current_user.id and application.project.creator_id != current_user.id:
        flash('У вас нет доступа к этому чату', 'danger')
        return redirect(url_for('chats'))

    # Определяем собеседника
    if current_user.id == application.user_id:
        # Вы - соискатель, собеседник - создатель проекта
        interlocutor = application.project.creator
        chat_type = 'applicant'
    else:
        # Вы - создатель проекта, собеседник - соискатель
        interlocutor = application.user
        chat_type = 'creator'

    return render_template('chat.html',
                           application=application,
                           project=application.project,
                           interlocutor=interlocutor,
                           chat_type=chat_type,
                           current_user=current_user)


# ---------- ОБРАБОТЧИКИ ОШИБОК ----------

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


# ========== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==========

with app.app_context():
    db.create_all()
    print("База данных инициализирована")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)