from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
import os
from database import db, login_manager, User, Project, Application
from werkzeug.security import generate_password_hash, check_password_hash
from forms import LoginForm, RegisterForm, ProjectForm

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
    user_projects = Project.query.filter_by(creator_id=current_user.id).all()
    applications = Application.query.filter_by(user_id=current_user.id).all()
    return render_template('profile.html',
                           user_projects=user_projects,
                           applications=applications,
                           current_user=current_user)


# ---------- ПРОЕКТЫ ----------

@app.route('/projects')
def projects():
    page = request.args.get('page', 1, type=int)
    per_page = 9  # Проектов на странице

    projects_list = Project.query.filter_by(status='active') \
        .order_by(Project.created_at.desc()) \
        .paginate(page=page, per_page=per_page, error_out=False)

    return render_template('projects.html',
                           projects=projects_list,
                           current_user=current_user)

@app.route('/project/<int:project_id>')
def project_detail(project_id):
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


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    from forms import EditProfileForm

    form = EditProfileForm()

    if form.validate_on_submit():
        current_user.full_name = form.full_name.data
        current_user.university = form.university.data
        current_user.faculty = form.faculty.data
        current_user.course = int(form.course.data)
        current_user.skills = form.skills.data
        current_user.bio = form.bio.data

        db.session.commit()
        flash('Профиль успешно обновлен!', 'success')
        return redirect(url_for('profile'))

    # Заполняем форму текущими данными
    if request.method == 'GET':
        form.full_name.data = current_user.full_name
        form.university.data = current_user.university
        form.faculty.data = current_user.faculty
        form.course.data = str(current_user.course)
        form.skills.data = current_user.skills
        form.bio.data = current_user.bio

    return render_template('edit_profile.html', form=form)

# ========== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==========

with app.app_context():
    db.create_all()


# В конец app.py перед if __name__ == '__main__' добавьте:

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)