from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
from datetime import datetime

db = SQLAlchemy()
login_manager = LoginManager()


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
    bio = db.Column(db.Text)  # Добавлено поле bio
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    projects = db.relationship('Project', backref='creator', lazy=True)
    applications = db.relationship('Application', backref='applicant', lazy=True)


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship('Application', backref='project', lazy=True)


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text)
    applied_role = db.Column(db.String(100))
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Убраны дублирующие relationship, используются backref из User и Project
    # user = db.relationship('User', foreign_keys=[user_id])  # УДАЛЕНО
    # project = db.relationship('Project', foreign_keys=[project_id])  # УДАЛЕНО


class Message(db.Model):
    __table_args__ = {'extend_existing': True}  # Важно для избежания конфликтов

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)  # ДОБАВЛЕНО - было пропущено!

    application = db.relationship('Application', backref='messages')
    sender = db.relationship('User', foreign_keys=[sender_id])

    def to_dict(self):
        """Преобразует сообщение в словарь для JSON"""
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'sender_name': self.sender.username if self.sender else 'Unknown',
            'content': self.content,
            'created_at': self.created_at.strftime('%H:%M %d.%m.%Y') if self.created_at else '',
            'is_read': self.is_read,
            'is_my_message': False  # Заполняется в коде при необходимости
        }