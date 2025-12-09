from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from models import db, User, Project, Application

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Формы
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')


class RegisterForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    full_name = StringField('ФИО', validators=[DataRequired()])
    university = StringField('ВУЗ', validators=[DataRequired()])
    faculty = StringField('Факультет', validators=[DataRequired()])
    course = SelectField('Курс', choices=[(str(i), str(i)) for i in range(1, 7)])
    skills = StringField('Навыки (через запятую)')
    submit = SubmitField('Зарегистрироваться')


class ProjectForm(FlaskForm):
    title = StringField('Название проекта', validators=[DataRequired()])
    description = TextAreaField('Описание', validators=[DataRequired()])
    category = SelectField('Категория', choices=[
        ('it', 'IT и Разработка'),
        ('business', 'Бизнес и Стартапы'),
        ('design', 'Дизайн и Креатив'),
        ('science', 'Наука и Исследования'),
        ('social', 'Социальные проекты'),
        ('other', 'Другое')
    ])
    needed_roles = TextAreaField('Требуемые роли (каждая с новой строки: "роль:уровень")')
    difficulty = SelectField('Сложность', choices=[
        ('beginner', 'Для начинающих'),
        ('intermediate', 'Средний уровень'),
        ('advanced', 'Продвинутый')
    ])
    location_type = SelectField('Формат работы', choices=[
        ('online', 'Онлайн'),
        ('offline', 'Очно'),
        ('hybrid', 'Гибрид')
    ])
    university_filter = StringField('Предпочтительный ВУЗ (оставьте пустым для всех)')
    faculty_filter = StringField('Предпочтительный факультет')
    estimated_duration = StringField('Примерная длительность')
    submit = SubmitField('Создать проект')


# Главная страница
@app.route('/')
def index():
    projects = Project.query.filter_by(status='active').order_by(Project.created_at.desc()).limit(6).all()
    stats = {
        'projects': Project.query.count(),
        'users': User.query.count(),
        'universities': db.session.query(User.university).distinct().count()
    }
    return render_template('index.html', projects=projects, stats=stats)


# Все проекты
@app.route('/projects')
def projects():
    category = request.args.get('category')
    university = request.args.get('university')
    difficulty = request.args.get('difficulty')

    query = Project.query.filter_by(status='active')

    if category:
        query = query.filter_by(category=category)
    if university:
        query = query.filter_by(university_filter=university)
    if difficulty:
        query = query.filter_by(difficulty=difficulty)

    projects = query.order_by(Project.created_at.desc()).all()
    universities = db.session.query(Project.university_filter).distinct().all()

    return render_template('projects.html',
                           projects=projects,
                           universities=[u[0] for u in universities if u[0]])


# Детали проекта
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

    has_applied = False
    if current_user.is_authenticated:
        has_applied = Application.query.filter_by(
            project_id=project_id,
            user_id=current_user.id
        ).first() is not None

    return render_template('project_detail.html',
                           project=project,
                           needed_roles=needed_roles,
                           has_applied=has_applied)


# Создание проекта
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


# Подача заявки
@app.route('/apply/<int:project_id>', methods=['POST'])
@login_required
def apply_to_project(project_id):
    role = request.form.get('role')
    message = request.form.get('message')

    existing = Application.query.filter_by(
        project_id=project_id,
        user_id=current_user.id
    ).first()

    if existing:
        flash('Вы уже подали заявку на этот проект', 'warning')
        return redirect(url_for('project_detail', project_id=project_id))

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


# Вход
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash('Вы успешно вошли!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверный email или пароль', 'danger')

    return render_template('login.html', form=form)


# Регистрация
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


# Выход
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


# Профиль
@app.route('/profile')
@login_required
def profile():
    user_projects = Project.query.filter_by(creator_id=current_user.id).all()
    applications = Application.query.filter_by(user_id=current_user.id).all()

    return render_template('profile.html',
                           user_projects=user_projects,
                           applications=applications)


# app.py - ДОПОЛНИТЕЛЬНЫЕ МАРШРУТЫ

# Управление заявками (принять/отклонить)
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
        # Здесь можно добавить логику добавления в команду
        flash(f'Заявка от {application.applicant.username} принята!', 'success')
    elif action == 'reject':
        application.status = 'rejected'
        flash(f'Заявка от {application.applicant.username} отклонена', 'info')

    db.session.commit()
    return redirect(url_for('project_detail', project_id=project.id))


# Удаление проекта
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


# Редактирование проекта
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


# Отмена заявки
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


# Поиск проектов с фильтрами
@app.route('/search', methods=['GET'])
def search_projects():
    search_query = request.args.get('q', '')
    category = request.args.get('category', '')
    university = request.args.get('university', '')
    difficulty = request.args.get('difficulty', '')

    query = Project.query.filter_by(status='active')

    if search_query:
        query = query.filter(
            (Project.title.ilike(f'%{search_query}%')) |
            (Project.description.ilike(f'%{search_query}%'))
        )

    if category and category != 'all':
        query = query.filter_by(category=category)

    if university and university != 'all':
        query = query.filter_by(university_filter=university)

    if difficulty and difficulty != 'all':
        query = query.filter_by(difficulty=difficulty)

    projects = query.order_by(Project.created_at.desc()).all()

    # Получаем уникальные значения для фильтров
    categories = db.session.query(Project.category).distinct().all()
    universities = db.session.query(Project.university_filter).distinct().all()
    difficulties = ['beginner', 'intermediate', 'advanced']

    return render_template('projects.html',
                           projects=projects,
                           search_query=search_query,
                           categories=[c[0] for c in categories if c[0]],
                           universities=[u[0] for u in universities if u[0]],
                           difficulties=difficulties,
                           selected_category=category,
                           selected_university=university,
                           selected_difficulty=difficulty)
# Запуск приложения
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5001)
