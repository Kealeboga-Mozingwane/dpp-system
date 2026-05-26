from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from app.models import User, AuditLog
from app import db
from datetime import datetime, timezone

users = Blueprint('users', __name__)

def log_action(action):
    entry = AuditLog(
        username=current_user.username,
        role=current_user.role,
        action=action,
        ip_address=request.remote_addr
    )
    db.session.add(entry)
    db.session.commit()

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != 'Admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return decorated

@users.route('/users')
@login_required
@admin_required
def index():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('users/index.html', users=all_users)

@users.route('/users/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('users.new'))
        if email and User.query.filter_by(email=email).first():
            flash('Email already in use.', 'danger')
            return redirect(url_for('users.new'))

        u = User(
            username  = username,
            full_name = request.form.get('full_name', '').strip(),
            email     = email,
            phone     = request.form.get('phone', '').strip(),
            role      = request.form.get('role', 'Prosecutor'),
            password  = generate_password_hash(request.form.get('password')),
            is_active = True
        )
        db.session.add(u)
        db.session.commit()
        log_action(f'Created user {username}')
        flash(f'User {username} created successfully.', 'success')
        return redirect(url_for('users.index'))
    return render_template('users/new.html')

@users.route('/users/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        user.full_name = request.form.get('full_name', '').strip()
        user.email     = request.form.get('email', '').strip()
        user.phone     = request.form.get('phone', '').strip()
        user.role      = request.form.get('role', user.role)
        user.is_active = request.form.get('is_active') == 'on'

        new_password = request.form.get('new_password', '').strip()
        if new_password:
            user.password = generate_password_hash(new_password)
            log_action(f'Reset password for {user.username}')

        db.session.commit()
        log_action(f'Updated user {user.username}')
        flash(f'User {user.username} updated.', 'success')
        return redirect(url_for('users.index'))
    return render_template('users/edit.html', user=user)

@users.route('/users/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('users.index'))
    user.is_active = not user.is_active
    db.session.commit()
    status = 'activated' if user.is_active else 'deactivated'
    log_action(f'User {user.username} {status}')
    flash(f'User {user.username} has been {status}.', 'success')
    return redirect(url_for('users.index'))

@users.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name', '').strip()
        current_user.email     = request.form.get('email', '').strip()
        current_user.phone     = request.form.get('phone', '').strip()
        new_password = request.form.get('new_password', '').strip()
        if new_password:
            from werkzeug.security import check_password_hash
            current_password = request.form.get('current_password', '')
            if not check_password_hash(current_user.password, current_password):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('users.profile'))
            current_user.password = generate_password_hash(new_password)
            flash('Password changed successfully.', 'success')
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('users.profile'))
    return render_template('users/profile.html')