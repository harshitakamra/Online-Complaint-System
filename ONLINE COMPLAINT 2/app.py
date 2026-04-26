import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

basedir = os.path.abspath(os.path.dirname(__file__))

db = SQLAlchemy()

def init_all_routes(app):
    @app.route('/')
    def index():
        if 'user_id' in session:
            usr_role = session.get('role')
            if usr_role == "admin":
                return redirect(url_for('admin_dashboard'))
            elif usr_role == 'department':
                return redirect(url_for('department_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        # default redirect for guests
        return redirect(url_for('student_login'))

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == "POST":
            nm = request.form.get('name')
            eml = request.form.get('email')
            pwd = request.form.get('password')
            cpwd = request.form.get('confirm_password')

            if not nm or not eml or not pwd or not cpwd:
                flash('Please fill out all the fields.', 'danger')
                return redirect(url_for('register'))

            if pwd != cpwd:
                flash("Passwords aren't matching up.", 'danger')
                return redirect(url_for('register'))

            check_eml = User.query.filter_by(email=eml).first()
            if check_eml:
                flash('This email is already in use.', 'warning')
                return redirect(url_for('student_login'))

            new_usr = User(name=nm, email=eml)
            new_usr.set_password(pwd)
            db.session.add(new_usr)
            db.session.commit()

            flash('You are registered! Log in now.', 'success')
            return redirect(url_for("student_login"))

        return render_template('register.html')

    @app.route('/login/student', methods=['GET', 'POST'])
    def student_login():
        if request.method == 'POST':
            return run_login_check('user', 'student_login', 'user_dashboard')
        return render_template('student_login.html')

    @app.route('/login/admin', methods=['GET', 'POST'])
    def admin_login():
        if request.method == 'POST':
            return run_login_check("admin", 'admin_login', 'admin_dashboard')
        return render_template('admin_login.html')

    @app.route('/login/department', methods=['GET', 'POST'])
    def department_login():
        if request.method == 'POST':
            return run_login_check('department', 'department_login', 'department_dashboard')
        return render_template('department_login.html')

    def run_login_check(role_need, login_rt, dash_rt):
        chk_email = request.form.get('email')
        chk_pwd = request.form.get('password')

        usr_obj = User.query.filter_by(email=chk_email).first()
        if usr_obj and usr_obj.check_password(chk_pwd):
            if usr_obj.role != role_need:
                flash("Wrong login portal for your account type.", 'danger')
                return redirect(url_for(login_rt))

            session['user_id'] = usr_obj.id
            session['role'] = usr_obj.role
            session['user_name'] = usr_obj.name

            flash("Successfully logged in.", 'success')
            return redirect(url_for(dash_rt))

        flash("Invalid credentials provided.", 'danger')
        return redirect(url_for(login_rt))

    @app.route('/logout')
    def logout():
        session.clear()
        flash("You have logged out.", 'success')
        return redirect(url_for('student_login'))

    @app.route('/user/dashboard')
    @login_required(role='user')
    def user_dashboard():
        uid = session['user_id']
        my_comps = Complaint.query.filter_by(user_id=uid).order_by(Complaint.created_at.desc()).all()
        return render_template('user_dashboard.html', complaints=my_comps)

    @app.route('/complaint/new', methods=['GET', 'POST'])
    @login_required(role='user')
    def submit_complaint():
        if request.method == 'POST':
            t = request.form.get('title')
            cat = request.form.get('category')
            desc = request.form.get('description')
            loc = request.form.get("location")

            if not t or not cat or not desc:
                flash("Missing some required details.", "danger")
                return redirect(url_for('submit_complaint'))

            new_c = Complaint(
                user_id=session['user_id'],
                title=t,
                category=cat,
                description=desc,
                location=loc,
            )
            db.session.add(new_c)
            db.session.commit()

            flash("Got your complaint!", 'success')
            return redirect(url_for('user_dashboard'))

        return render_template('submit_complaint.html')

    @app.route('/complaint/<int:complaint_id>')
    @login_required()
    def view_complaint(complaint_id):
        c_obj = Complaint.query.get_or_404(complaint_id)

        # block regular users from seeing other people's stuff
        if session.get('role') == 'user' and c_obj.user_id != session['user_id']:
            flash("No permission to see this.", 'danger')
            return redirect(url_for('user_dashboard'))
            
        dept_list = []
        if session.get('role') == 'admin':
            dept_list = User.query.filter_by(role='department').all()

        return render_template('complaint_detail.html', complaint=c_obj, departments=dept_list)

    @app.route('/admin/dashboard')
    @login_required(role='admin')
    def admin_dashboard():
        f_stat = request.args.get('status')
        q = Complaint.query.order_by(Complaint.created_at.desc())
        if f_stat:
            q = q.filter_by(status=f_stat)
        all_comps = q.all()
        return render_template('admin_dashboard.html', complaints=all_comps)

    @app.route('/admin/complaint/<int:complaint_id>/update', methods=['POST'])
    @login_required(role="admin")
    def admin_update_complaint(complaint_id):
        c_record = Complaint.query.get_or_404(complaint_id)
        
        upd_status = request.form.get('status')
        upd_remarks = request.form.get('admin_remarks')
        upd_dept_id = request.form.get('assigned_department_id')

        if upd_status:
            c_record.status = upd_status
        c_record.admin_remarks = upd_remarks
        
        if upd_dept_id:
            c_record.assigned_department_id = upd_dept_id

        db.session.commit()
        flash("Done updating.", 'success')
        return redirect(url_for('admin_dashboard'))

    @app.route('/department/dashboard')
    @login_required(role='department')
    def department_dashboard():
        f_stat2 = request.args.get('status')
        dept_q = Complaint.query.filter_by(assigned_department_id=session['user_id']).order_by(Complaint.created_at.desc())
        
        if f_stat2:
            dept_q = dept_q.filter_by(department_status=f_stat2)
            
        return render_template('department_dashboard.html', complaints=dept_q.all())

    @app.route('/department/complaint/<int:complaint_id>')
    @login_required(role='department')
    def department_view_complaint(complaint_id):
        c_item = Complaint.query.get_or_404(complaint_id)
        if c_item.assigned_department_id != session['user_id']:
            flash("Not assigned to your department.", "danger")
            return redirect(url_for('department_dashboard'))
            
        return render_template('department_complaint_detail.html', complaint=c_item)

    @app.route('/department/complaint/<int:complaint_id>/update', methods=['POST'])
    @login_required(role='department')
    def department_update_complaint(complaint_id):
        c_item = Complaint.query.get_or_404(complaint_id)
        if c_item.assigned_department_id != session['user_id']:
            flash('Access denied.', 'danger')
            return redirect(url_for('department_dashboard'))

        d_stat = request.form.get('department_status')
        d_rem = request.form.get('department_remarks')

        if d_stat:
            c_item.department_status = d_stat
            
        c_item.department_remarks = d_rem
        
        db.session.commit()
        flash("Saved status.", 'success')
        return redirect(url_for('department_dashboard'))

# app setup and db stuff
def create_app():
    core_app = Flask(__name__)
    core_app.config['SECRET_KEY'] = 'some-random-secret-key-here'

    core_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'complaints.db')
    core_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(core_app)

    with core_app.app_context():
        db.drop_all()   # 🔥 ensures no old schema
        db.create_all()
        setup_default_accounts()

    init_all_routes(core_app)
    return core_app

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.now)

    complaints = db.relationship('Complaint', foreign_keys='Complaint.user_id', backref='user', lazy=True)
    department_complaints = db.relationship('Complaint', foreign_keys='Complaint.assigned_department_id', backref='department', lazy=True)

    def set_password(self, clear_pw):
        self.password_hash = generate_password_hash(clear_pw)

    def check_password(self, clear_pw):
        return check_password_hash(self.password_hash, clear_pw)

class Complaint(db.Model):
    __tablename__ = 'complaints'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(100))
    status = db.Column(db.String(20), default='Pending')
    admin_remarks = db.Column(db.Text)
    
    assigned_department_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    department_status = db.Column(db.String(20), default='Pending')
    department_remarks = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

def setup_default_accounts():
    adm_mail = "admin@complaints.com"
    sys_admin = User.query.filter_by(email=adm_mail).first()
    
    if not sys_admin:
        sys_admin = User(name='Admin', email=adm_mail, role='admin')
        sys_admin.set_password('admin123')
        db.session.add(sys_admin)
        db.session.commit()

    depts = ['IT Department', 'HR Department', 'Maintenance']
    for d_name in depts:
        em = f"{d_name.split()[0].lower()}@complaints.com"
        d_usr = User.query.filter_by(email=em).first()
        if not d_usr:
            d_usr = User(name=d_name, email=em, role='department')
            d_usr.set_password('dept123')
            db.session.add(d_usr)
            
    db.session.commit()

def login_required(role=None):
    def wrapper(func):
        @wraps(func)
        def decorated_view(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('student_login'))
            if role and session.get('role') != role:
                flash("You aren't authorized to see this.", 'danger')
                return redirect(url_for('index'))
            return func(*args, **kwargs)
        return decorated_view
    return wrapper

if __name__ == '__main__':
    application = create_app()
    application.run(host='0.0.0.0', port=5001, debug=True)