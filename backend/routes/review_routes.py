from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import ReviewModel, JobModel, UserModel, AssignmentModel, db_cursor
from services.auth_service import login_required, get_current_user
from services.reliability_service import recalculate_user_rating

review_bp = Blueprint('review_routes', __name__)

@review_bp.route('/reviews')
@login_required
def my_reviews():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.login'))

    received_reviews = ReviewModel.get_by_reviewed_user(user['id'])

    with db_cursor() as cur:
        cur.execute("""
            SELECT r.*, reviewed.name as reviewed_name, j.title as job_title, j.category as job_category
            FROM reviews r
            JOIN users reviewed ON r.reviewed_user_id = reviewed.id
            JOIN jobs j ON r.job_id = j.id
            WHERE r.reviewer_id = ?
            ORDER BY r.created_at DESC
        """, (user['id'],))
        given_reviews = [dict(row) for row in cur.fetchall()]

    return render_template('reviews.html', user=user, received_reviews=received_reviews, given_reviews=given_reviews)

@review_bp.route('/review/<int:job_id>/<int:user_id>', methods=['GET', 'POST'])
@login_required
def submit_review(job_id, user_id):
    reviewer = get_current_user()
    if not reviewer:
        return redirect(url_for('auth_routes.login'))

    if reviewer['id'] == user_id:
        flash("You cannot review yourself.", "warning")
        return redirect(url_for('job_routes.my_jobs'))

    job = JobModel.get_by_id(job_id)
    if not job:
        flash("Job not found.", "danger")
        return redirect(url_for('job_routes.my_jobs'))

    reviewed_user = UserModel.get_by_id(user_id)
    if not reviewed_user:
        flash("User to review not found.", "danger")
        return redirect(url_for('job_routes.my_jobs'))

    # Check if this reviewer has already reviewed this user for this job
    if ReviewModel.has_reviewed(job_id, reviewer['id'], user_id):
        flash(f"You have already submitted a review for {reviewed_user['name']} on this job.", "info")
        return redirect(url_for('profile_routes.public_profile', user_id=user_id))

    if request.method == 'POST':
        rating_val = request.form.get('rating')
        review_text = request.form.get('review', '').strip()

        try:
            rating = int(rating_val)
            if rating < 1 or rating > 5:
                raise ValueError()
        except (ValueError, TypeError):
            flash("Please provide a valid rating between 1 and 5 stars.", "danger")
            return render_template('reviews.html', job=job, target_user=reviewed_user, is_submission=True)

        ReviewModel.create(job_id, reviewer['id'], user_id, rating, review_text)
        recalculate_user_rating(user_id)

        flash(f"Thank you! Your {rating}-star review for {reviewed_user['name']} has been published.", "success")
        return redirect(url_for('profile_routes.public_profile', user_id=user_id))

    return render_template('reviews.html', job=job, target_user=reviewed_user, is_submission=True)
