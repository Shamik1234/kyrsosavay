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