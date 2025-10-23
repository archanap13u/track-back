from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Employee(db.Model):
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    department = db.Column(db.String(100))
    role = db.Column(db.String(100))
    pc_identifier = db.Column(db.String(200))
    status = db.Column(db.String(20), default='offline')
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    monitoring_consent = db.Column(db.Boolean, default=False)
    consent_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    work_sessions = db.relationship('WorkSession', backref='employee', lazy=True, cascade='all, delete-orphan')
    activities = db.relationship('ActivityLog', backref='employee', lazy=True, cascade='all, delete-orphan')

class WorkSession(db.Model):
    __tablename__ = 'work_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    clock_in = db.Column(db.DateTime, nullable=False)
    clock_out = db.Column(db.DateTime)
    total_active_time = db.Column(db.Float, default=0.0)
    total_idle_time = db.Column(db.Float, default=0.0)
    productivity_score = db.Column(db.Float, default=0.0)
    date = db.Column(db.Date, nullable=False)

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    activity_type = db.Column(db.String(50))
    application_name = db.Column(db.String(200))
    window_title = db.Column(db.String(500))
    url = db.Column(db.String(1000))
    category = db.Column(db.String(50))
    duration = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Admin(db.Model):
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='admin')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)