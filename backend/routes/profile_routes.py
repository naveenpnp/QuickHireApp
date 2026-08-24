from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import UserModel, ReviewModel, db_cursor
from services.auth_service import login_required, get_current_user

profile_bp = Blueprint('profile_routes', __name__)

@profile_bp.route('/profile')
@login_required
def profile():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.login'))

    user_id = user['id']
    reviews = ReviewModel.get_by_reviewed_user(user_id)

    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM jobs WHERE poster_id = ?", (user_id,))
        jobs_posted_count = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM job_assignments ja
            JOIN jobs j ON ja.job_id = j.id
            WHERE j.poster_id = ? AND ja.status = 'Completed'
        """, (user_id,))
        completed_hires_count = cur.fetchone()[0]

        cur.execute("SELECT * FROM jobs WHERE poster_id = ? AND status IN ('Available', 'Worker Selected', 'In Progress') ORDER BY created_at DESC", (user_id,))
        active_jobs = [dict(r) for r in cur.fetchall()]

    return render_template(
        'profile.html',
        profile_user=user,
        is_own_profile=True,
        reviews=reviews,
        jobs_posted_count=jobs_posted_count,
        completed_hires_count=completed_hires_count,
        active_jobs=active_jobs
    )

@profile_bp.route('/profile/<int:user_id>')
def public_profile(user_id):
    current_user = get_current_user()
    profile_user = UserModel.get_by_id(user_id)
    if not profile_user:
        flash("User not found.", "danger")
        return redirect(url_for('job_routes.jobs'))

    is_own_profile = current_user and (current_user['id'] == user_id)
    reviews = ReviewModel.get_by_reviewed_user(user_id)

    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM jobs WHERE poster_id = ?", (user_id,))
        jobs_posted_count = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM job_assignments ja
            JOIN jobs j ON ja.job_id = j.id
            WHERE j.poster_id = ? AND ja.status = 'Completed'
        """, (user_id,))
        completed_hires_count = cur.fetchone()[0]

        cur.execute("SELECT * FROM jobs WHERE poster_id = ? AND status = 'Available' ORDER BY created_at DESC", (user_id,))
        active_jobs = [dict(r) for r in cur.fetchall()]

    return render_template(
        'profile.html',
        profile_user=profile_user,
        is_own_profile=is_own_profile,
        reviews=reviews,
        jobs_posted_count=jobs_posted_count,
        completed_hires_count=completed_hires_count,
        active_jobs=active_jobs
    )

@profile_bp.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.login'))

    name = request.form.get('name', '').strip()
    location = request.form.get('location', '').strip()
    skills = request.form.get('skills', '').strip()
    phone = request.form.get('phone', '').strip()

    if not name:
        flash("Name cannot be empty.", "danger")
        return redirect(url_for('profile_routes.profile'))

    UserModel.update_profile(user['id'], name, location, skills, phone=phone)
    flash("Profile updated successfully!", "success")
    return redirect(url_for('profile_routes.profile'))
