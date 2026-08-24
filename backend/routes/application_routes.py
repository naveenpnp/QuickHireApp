from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import ApplicationModel, JobModel, AssignmentModel, UserModel, db_cursor
from services.auth_service import login_required, get_current_user
from datetime import datetime

application_bp = Blueprint('application_routes', __name__)

@application_bp.route('/apply/<int:job_id>', methods=['POST', 'GET'])
@login_required
def apply(job_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.login'))

    job = JobModel.get_by_id(job_id)
    if not job:
        flash("Job not found.", "danger")
        return redirect(url_for('job_routes.jobs'))

    # Rule 1: A user cannot apply to their own job
    if job['poster_id'] == user['id']:
        flash("You cannot apply to your own job posting.", "warning")
        return redirect(url_for('job_routes.job_details', job_id=job_id))

    # Rule 2: A user cannot apply twice to the same job
    existing = ApplicationModel.get_by_job_and_worker(job_id, user['id'])
    if existing:
        flash("You have already applied for this job.", "info")
        return redirect(url_for('job_routes.job_details', job_id=job_id))

    if job['status'] not in ('Available',):
        flash("This job is no longer accepting new applications.", "warning")
        return redirect(url_for('job_routes.job_details', job_id=job_id))

    ApplicationModel.create(job_id, user['id'])
    flash(f"Application submitted successfully for '{job['title']}'!", "success")
    return redirect(url_for('application_routes.applications'))

@application_bp.route('/applications')
@login_required
def applications():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.login'))

    user_applications = ApplicationModel.get_by_worker(user['id'])
    return render_template('applications.html', applications=user_applications)

@application_bp.route('/select-worker/<int:application_id>', methods=['POST'])
@login_required
def select_worker(application_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.login'))

    app = ApplicationModel.get_by_id(application_id)
    if not app:
        flash("Application not found.", "danger")
        return redirect(url_for('job_routes.jobs'))

    job = JobModel.get_by_id(app['job_id'])
    if not job:
        flash("Job not found.", "danger")
        return redirect(url_for('job_routes.jobs'))

    # Check that current user is the poster
    if job['poster_id'] != user['id']:
        flash("Unauthorized action. You are not the poster of this job.", "danger")
        return redirect(url_for('job_routes.job_details', job_id=job['id']))

    with db_cursor(commit=True) as cur:
        # Check current active assignments count
        cur.execute("""
            SELECT COUNT(*) FROM job_assignments
            WHERE job_id = ? AND status != 'No Show'
        """, (job['id'],))
        current_assigned = cur.fetchone()[0]

        # Rule 3: A job cannot have more selected workers than required_workers
        if current_assigned >= job['required_workers']:
            flash(f"All {job['required_workers']} worker slot(s) for this job are already filled.", "warning")
            return redirect(url_for('job_routes.job_details', job_id=job['id']))

        # Update application status
        cur.execute("""
            UPDATE applications
            SET status = 'Selected', selected_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (application_id,))

        # Create Job Assignment
        cur.execute("""
            INSERT INTO job_assignments (job_id, worker_id, status)
            VALUES (?, ?, 'Assigned')
        """, (job['id'], app['worker_id']))

        new_assigned_count = current_assigned + 1

        # If all slots filled, auto-reject other pending applications and update job status
        if new_assigned_count >= job['required_workers']:
            cur.execute("""
                UPDATE applications
                SET status = 'Rejected'
                WHERE job_id = ? AND status = 'Applied'
            """, (job['id'],))
            cur.execute("UPDATE jobs SET status = 'Worker Selected' WHERE id = ?", (job['id'],))

    worker = UserModel.get_by_id(app['worker_id'])
    worker_name = worker['name'] if worker else 'Worker'
    flash(f"Worker {worker_name} has been selected! Assignment is now ready to start.", "success")
    return redirect(url_for('job_routes.job_details', job_id=job['id']))
