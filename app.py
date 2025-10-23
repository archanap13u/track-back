from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, date, timedelta
import jwt
import os
from functools import wraps
from database import db, Employee, WorkSession, ActivityLog, Admin

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 
    'postgresql://tracker_user:password@localhost:5432/activity_tracker'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-this')

CORS(app)
db.init_app(app)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        try:
            token = token.replace('Bearer ', '')
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = Admin.query.get(data['user_id'])
            if not current_user:
                return jsonify({'error': 'Invalid user'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    admin = Admin.query.filter_by(username=data.get('username')).first()
    
    if admin and admin.check_password(data.get('password')):
        token = jwt.encode({
            'user_id': admin.id,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.config['SECRET_KEY'])
        
        return jsonify({
            'token': token,
            'user': {
                'id': admin.id,
                'username': admin.username,
                'email': admin.email,
                'role': admin.role
            }
        })
    
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/employees', methods=['GET'])
@token_required
def get_employees(current_user):
    employees = Employee.query.all()
    return jsonify({
        'employees': [{
            'id': e.id,
            'employee_id': e.employee_id,
            'name': e.name,
            'email': e.email,
            'department': e.department,
            'role': e.role,
            'status': e.status,
            'last_activity': e.last_activity.isoformat() if e.last_activity else None,
            'monitoring_consent': e.monitoring_consent
        } for e in employees]
    })

@app.route('/api/employees/<int:emp_id>/activity', methods=['GET'])
@token_required
def get_employee_activity(current_user, emp_id):
    date_param = request.args.get('date', date.today().isoformat())
    target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
    
    session = WorkSession.query.filter_by(
        employee_id=emp_id,
        date=target_date
    ).first()
    
    activities = ActivityLog.query.filter(
        ActivityLog.employee_id == emp_id,
        db.func.date(ActivityLog.timestamp) == target_date
    ).order_by(ActivityLog.timestamp.desc()).limit(100).all()
    
    return jsonify({
        'session': {
            'clock_in': session.clock_in.isoformat() if session else None,
            'clock_out': session.clock_out.isoformat() if session and session.clock_out else None,
            'active_time': session.total_active_time if session else 0,
            'idle_time': session.total_idle_time if session else 0,
            'productivity_score': session.productivity_score if session else 0
        },
        'activities': [{
            'type': a.activity_type,
            'application': a.application_name,
            'window_title': a.window_title,
            'url': a.url,
            'category': a.category,
            'duration': a.duration,
            'timestamp': a.timestamp.isoformat()
        } for a in activities]
    })

@app.route('/api/agent/register', methods=['POST'])
def register_agent():
    data = request.json
    
    employee = Employee.query.filter_by(
        employee_id=data.get('employee_id')
    ).first()
    
    if not employee:
        return jsonify({'error': 'Employee not found'}), 404
    
    employee.pc_identifier = data.get('pc_identifier')
    employee.monitoring_consent = data.get('consent', False)
    employee.consent_date = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'employee_id': employee.id,
        'tracking_enabled': employee.monitoring_consent
    })

@app.route('/api/agent/heartbeat', methods=['POST'])
def agent_heartbeat():
    data = request.json
    
    employee = Employee.query.filter_by(
        pc_identifier=data.get('pc_identifier')
    ).first()
    
    if not employee:
        return jsonify({'error': 'Employee not registered'}), 404
    
    employee.status = data.get('status', 'active')
    employee.last_activity = datetime.utcnow()
    
    today = date.today()
    session = WorkSession.query.filter_by(
        employee_id=employee.id,
        date=today
    ).first()
    
    if not session:
        session = WorkSession(
            employee_id=employee.id,
            clock_in=datetime.utcnow(),
            date=today
        )
        db.session.add(session)
    
    session.total_active_time = data.get('active_time', 0)
    session.total_idle_time = data.get('idle_time', 0)
    session.productivity_score = data.get('productivity_score', 0)
    
    if data.get('current_app'):
        activity = ActivityLog(
            employee_id=employee.id,
            activity_type='app_usage',
            application_name=data.get('current_app'),
            window_title=data.get('window_title'),
            category=data.get('app_category', 'neutral'),
            duration=data.get('duration', 0)
        )
        db.session.add(activity)
    
    db.session.commit()
    
    return jsonify({'success': True, 'status': 'recorded'})

@app.route('/api/agent/activity', methods=['POST'])
def log_activity():
    data = request.json
    
    employee = Employee.query.filter_by(
        pc_identifier=data.get('pc_identifier')
    ).first()
    
    if not employee:
        return jsonify({'error': 'Employee not registered'}), 404
    
    if data.get('applications'):
        for app_data in data.get('applications'):
            activity = ActivityLog(
                employee_id=employee.id,
                activity_type='app_usage',
                application_name=app_data.get('name'),
                window_title=app_data.get('window_title'),
                category=app_data.get('category'),
                duration=app_data.get('duration')
            )
            db.session.add(activity)
    
    if data.get('websites'):
        for web_data in data.get('websites'):
            activity = ActivityLog(
                employee_id=employee.id,
                activity_type='website_visit',
                url=web_data.get('url'),
                category=web_data.get('category'),
                duration=web_data.get('duration')
            )
            db.session.add(activity)
    
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/analytics/productivity', methods=['GET'])
@token_required
def get_productivity_analytics(current_user):
    today = date.today()
    
    sessions = WorkSession.query.filter_by(date=today).all()
    
    active_employees = len([s for s in sessions if s.employee.status == 'active'])
    avg_productivity = sum(s.productivity_score for s in sessions) / len(sessions) if sessions else 0
    total_hours = sum(s.total_active_time for s in sessions)
    total_idle = sum(s.total_idle_time for s in sessions)
    
    return jsonify({
        'active_employees': active_employees,
        'total_employees': Employee.query.count(),
        'avg_productivity': round(avg_productivity, 2),
        'total_work_hours': round(total_hours, 2),
        'total_idle_time': round(total_idle, 2),
        'date': today.isoformat()
    })

@app.route('/api/analytics/applications', methods=['GET'])
@token_required
def get_application_analytics(current_user):
    today = date.today()
    
    apps = db.session.query(
        ActivityLog.application_name,
        db.func.sum(ActivityLog.duration).label('total_time'),
        ActivityLog.category
    ).filter(
        db.func.date(ActivityLog.timestamp) == today,
        ActivityLog.activity_type == 'app_usage',
        ActivityLog.application_name.isnot(None)
    ).group_by(
        ActivityLog.application_name,
        ActivityLog.category
    ).order_by(db.desc('total_time')).limit(10).all()
    
    return jsonify([{
        'application': app.application_name,
        'time_hours': round(app.total_time / 3600, 2),
        'category': app.category
    } for app in apps])

@app.cli.command()
def init_db():
    db.create_all()
    print("✅ Database initialized successfully!")

@app.cli.command()
def create_admin():
    admin = Admin(
        username='admin',
        email='admin@company.com',
        role='admin'
    )
    admin.set_password('admin123')
    db.session.add(admin)
    db.session.commit()
    print("✅ Admin user created!")
    print("Username: admin")
    print("Password: admin123")
    print("⚠️  CHANGE THE PASSWORD IN PRODUCTION!")

@app.cli.command()
def seed_data():
    employees_data = [
        {'employee_id': 'EMP001', 'name': 'Sarah Johnson', 'email': 'sarah@company.com', 'department': 'Engineering', 'role': 'Senior Developer'},
        {'employee_id': 'EMP002', 'name': 'Michael Chen', 'email': 'michael@company.com', 'department': 'Product', 'role': 'Product Manager'},
        {'employee_id': 'EMP003', 'name': 'Emily Davis', 'email': 'emily@company.com', 'department': 'Design', 'role': 'UX Designer'},
    ]
    
    for emp_data in employees_data:
        emp = Employee(**emp_data)
        emp.monitoring_consent = True
        emp.consent_date = datetime.utcnow()
        db.session.add(emp)
    
    db.session.commit()
    print("✅ Sample data created!")

from waitress import serve

if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=5000)
    