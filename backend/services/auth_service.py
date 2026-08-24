from functools import wraps
from flask import session, redirect, url_for, flash, request
from werkzeug.security import generate_password_hash, check_password_hash
from models import UserModel

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth_routes.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return UserModel.get_by_id(user_id)

def login_user(user, selected_role=None):
    session['user_id'] = user['id']
    session['user_name'] = user['name']
    session['user_email'] = user['email']
    session['role'] = selected_role or user.get('role') or 'worker'
    UserModel.update_online_status(user['id'], True)

def logout_user():
    user_id = session.get('user_id')
    if user_id:
        UserModel.update_online_status(user_id, False)
    session.clear()

def hash_password(password):
    return generate_password_hash(password)

def verify_password(password_hash, password):
    return check_password_hash(password_hash, password)
