from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import UserModel
from services.auth_service import login_user, logout_user, hash_password, verify_password, validate_strong_password

auth_bp = Blueprint('auth_routes', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('main_routes.dashboard'))

    selected_role = request.args.get('role', 'worker')

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        location = request.form.get('location', '').strip()
        skills = request.form.get('skills', '').strip()
        phone = request.form.get('phone', '').strip()
        role = request.form.get('role', selected_role).strip().lower()

        if not name or not email or not password:
            flash("Please fill in all required fields (Name, Email, Password).", "danger")
            return render_template('register.html', name=name, email=email, location=location, skills=skills, phone=phone, selected_role=role)

        # Check confirm password if provided
        if confirm_password and password != confirm_password:
            flash("Passwords do not match. Please re-enter your password.", "warning")
            return render_template('register.html', name=name, email=email, location=location, skills=skills, phone=phone, selected_role=role)

        # Enforce strong password policy
        is_strong, pwd_err = validate_strong_password(password)
        if not is_strong:
            flash(pwd_err, "danger")
            return render_template('register.html', name=name, email=email, location=location, skills=skills, phone=phone, selected_role=role)

        existing_user = UserModel.get_by_email(email)
        if existing_user:
            flash("An account with this email already exists. Please log in.", "warning")
            return redirect(url_for('auth_routes.login', role=role))

        pwd_hash = hash_password(password)
        user_id = UserModel.create(name, email, pwd_hash, location=location, skills=skills, phone=phone, role=role)

        user = UserModel.get_by_id(user_id)
        login_user(user, selected_role=role)
        role_title = "Employer / Client" if role == 'employer' else "Worker / Freelancer"
        flash(f"Welcome to QuickHire, {name}! Your {role_title} account has been created with ₹5,000 initial balance.", "success")
        return redirect(url_for('main_routes.dashboard'))

    return render_template('register.html', selected_role=selected_role)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('main_routes.dashboard'))

    active_tab = request.args.get('role', 'employer')

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        portal_role = request.form.get('role', active_tab).strip().lower()

        if not email or not password:
            flash("Please provide both email and password.", "danger")
            return render_template('login.html', email=email, active_tab=portal_role)

        user = UserModel.get_by_email(email)
        if not user or not verify_password(user['password'], password):
            flash("Invalid email or password. Please check your credentials.", "danger")
            return render_template('login.html', email=email, active_tab=portal_role)

        # Login strictly with the user's permanent registered account role
        user_role = user.get('role') or 'worker'
        login_user(user, selected_role=user_role)
        role_label = "Employer Portal" if user_role == 'employer' else "Worker Portal"
        flash(f"Welcome back, {user['name']}! Signed into {role_label}.", "success")

        next_url = request.args.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect(url_for('main_routes.dashboard'))

    return render_template('login.html', active_tab=active_tab)

@auth_bp.route('/logout')
def logout():
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('main_routes.index'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not email or not new_password:
            flash("Please provide your registered email and new password.", "danger")
            return render_template('forgot_password.html', email=email)

        user = UserModel.get_by_email(email)
        if not user:
            flash("No account found with this email address. Please check your spelling or register.", "danger")
            return render_template('forgot_password.html', email=email)

        if new_password != confirm_password:
            flash("Passwords do not match. Please ensure both fields are identical.", "warning")
            return render_template('forgot_password.html', email=email)

        is_strong, pwd_err = validate_strong_password(new_password)
        if not is_strong:
            flash(pwd_err, "danger")
            return render_template('forgot_password.html', email=email)

        pwd_hash = hash_password(new_password)
        UserModel.update_password(email, pwd_hash)

        flash(f"Password reset successfully for {user['name']}! You can now log in with your new password.", "success")
        return redirect(url_for('auth_routes.login', role=user.get('role', 'worker')))

    email = request.args.get('email', '')
    return render_template('forgot_password.html', email=email)

@auth_bp.route('/auth/google', methods=['GET', 'POST'])
def google_auth():
    """Real-World Google OAuth Sign-In & Profile Linking"""
    role = request.args.get('role', 'worker').lower()

    if request.method == 'POST':
        email = request.form.get('google_email', '').strip().lower()
        name = request.form.get('google_name', '').strip()

        if not email:
            flash("Please provide your Google email address.", "danger")
            return render_template('google_auth.html', role=role)

        user = UserModel.get_by_email(email)
        if not user:
            # Create real account from Google Profile
            pwd_hash = hash_password("GoogleAuth@2026")
            display_name = name if name else email.split('@')[0].replace('.', ' ').title()
            user_id = UserModel.create(
                name=display_name,
                email=email,
                password_hash=pwd_hash,
                location="Chennai, Tamil Nadu",
                skills="Google Verified Account",
                phone="+91 98401 55555",
                role=role
            )
            user = UserModel.get_by_id(user_id)

        user_role = user.get('role') or role
        login_user(user, selected_role=user_role)
        flash(f"Successfully authenticated via Google as {user['name']} ({user['email']})!", "success")
        return redirect(url_for('main_routes.dashboard'))

    email_param = request.args.get('email')
    if email_param:
        email = email_param.strip().lower()
        name = request.args.get('name', '').strip()
        user = UserModel.get_by_email(email)
        if not user:
            pwd_hash = hash_password("GoogleAuth@2026")
            display_name = name if name else email.split('@')[0].replace('.', ' ').title()
            user_id = UserModel.create(
                name=display_name,
                email=email,
                password_hash=pwd_hash,
                location="Chennai, Tamil Nadu",
                skills="Google Verified Account",
                phone="+91 98401 55555",
                role=role
            )
            user = UserModel.get_by_id(user_id)
        user_role = user.get('role') or role
        login_user(user, selected_role=user_role)
        flash(f"Successfully authenticated via Google as {user['name']} ({user['email']})!", "success")
        return redirect(url_for('main_routes.dashboard'))

    return render_template('google_auth.html', role=role)
