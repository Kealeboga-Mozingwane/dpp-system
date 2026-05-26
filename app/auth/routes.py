from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app.models import User, Recording, Transcript, Matter, AuditLog
from app import db
from datetime import datetime, timezone

auth = Blueprint('auth', __name__)

def log_action(action):
    entry = AuditLog(
        username=current_user.username if current_user.is_authenticated else 'system',
        role=current_user.role if current_user.is_authenticated else '',
        action=action,
        ip_address=request.remote_addr
    )
    db.session.add(entry)
    db.session.commit()

@auth.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    return redirect(url_for('auth.login'))

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password) and user.is_active:
            login_user(user)
            user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
            db.session.commit()
            log_action(f'Logged in')
            flash('Welcome back, ' + (user.full_name or user.username) + '.', 'success')
            return redirect(url_for('auth.dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('auth/login.html')

@auth.route('/logout')
@login_required
def logout():
    log_action('Logged out')
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('auth.login'))

@auth.route('/dashboard')
@login_required
def dashboard():
    stats = {
        'recordings': Recording.query.count(),
        'transcripts': Transcript.query.count(),
        'matters': Matter.query.filter_by(status='Active').count(),
        'users': User.query.filter_by(is_active=True).count(),
    }
    recent_recordings = Recording.query.order_by(
        Recording.created_at.desc()).limit(5).all()
    recent_transcripts = Transcript.query.order_by(
        Transcript.created_at.desc()).limit(5).all()
    return render_template('auth/dashboard.html',
        stats=stats,
        recent_recordings=recent_recordings,
        recent_transcripts=recent_transcripts)