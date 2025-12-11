from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from wtforms import ValidationError
from database import User


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')


class RegisterForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Повторите пароль',
                                     validators=[DataRequired(), EqualTo('password')])
    full_name = StringField('ФИО', validators=[DataRequired()])
    university = StringField('ВУЗ', validators=[DataRequired()])
    faculty = StringField('Факультет', validators=[DataRequired()])
    course = SelectField('Курс', choices=[
        ('1', '1 курс'), ('2', '2 курс'), ('3', '3 курс'),
        ('4', '4 курс'), ('5', '5 курс'), ('6', '6 курс')
    ], validators=[DataRequired()])
    skills = StringField('Навыки (через запятую)')
    submit = SubmitField('Зарегистрироваться')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Этот логин уже занят')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Этот email уже зарегистрирован')
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
# В конец forms.py добавьте:

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
    needed_roles = TextAreaField('Требуемые роли (каждая с новой строки: "роль:уровень")',
                                 validators=[DataRequired()])
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

class ApplicationForm(FlaskForm):
    applied_role = SelectField('На какую роль вы претендуете?', choices=[])
    message = TextAreaField('Расскажите о себе', validators=[DataRequired()])
    submit = SubmitField('Подать заявку')