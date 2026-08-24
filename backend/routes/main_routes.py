from flask import Blueprint, render_template, session, redirect, url_for
from models import UserModel, JobModel, ApplicationModel, AssignmentModel, db_cursor
from services.auth_service import login_required, get_current_user

main_bp = Blueprint('main_routes', __name__)

@main_bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('main_routes.dashboard'))
    
    # Fetch recent urgent and available jobs for public hero display
    urgent_jobs = JobModel.get_all(urgent_only=True, status='Available')[:3]
    recent_jobs = JobModel.get_all(status='Available')[:6]
    
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM jobs WHERE status = 'Completed'")
        completed_jobs_count = cur.fetchone()[0]

    return render_template('index.html', urgent_jobs=urgent_jobs, recent_jobs=recent_jobs,
                           total_users=total_users, completed_jobs_count=completed_jobs_count)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.logout'))

    user_id = user['id']

    # Statistics for dashboard
    with db_cursor() as cur:
        # Jobs posted by user
        cur.execute("SELECT COUNT(*) FROM jobs WHERE poster_id = ?", (user_id,))
        posted_count = cur.fetchone()[0]

        # Active applications sent by user
        cur.execute("SELECT COUNT(*) FROM applications WHERE worker_id = ?", (user_id,))
        apps_count = cur.fetchone()[0]

        # Active work assignments where user is worker
        cur.execute("""
            SELECT ja.*, j.title as job_title, j.category, j.location, j.job_date, j.start_time, j.end_time,
                   j.payment as job_payment, u.name as poster_name
            FROM job_assignments ja
            JOIN jobs j ON ja.job_id = j.id
            JOIN users u ON j.poster_id = u.id
            WHERE ja.worker_id = ? AND ja.status IN ('Assigned', 'In Progress', 'Awaiting Confirmation')
            ORDER BY ja.id DESC
        """, (user_id,))
        active_worker_tasks = [dict(row) for row in cur.fetchall()]

        # Tasks where user is poster and worker has marked completed (Awaiting Confirmation)
        cur.execute("""
            SELECT ja.*, j.title as job_title, j.category, j.location, j.payment as job_payment,
                   worker.name as worker_name, worker.reliability_score as worker_reliability
            FROM job_assignments ja
            JOIN jobs j ON ja.job_id = j.id
            JOIN users worker ON ja.worker_id = worker.id
            WHERE j.poster_id = ? AND ja.status = 'Awaiting Confirmation'
            ORDER BY ja.id DESC
        """, (user_id,))
        pending_confirmations = [dict(row) for row in cur.fetchall()]

        # Active jobs posted by user that need workers or have applicants
        cur.execute("""
            SELECT j.*, 
                   (SELECT COUNT(*) FROM applications WHERE job_id = j.id) as applicant_count,
                   (SELECT COUNT(*) FROM job_assignments WHERE job_id = j.id AND status != 'No Show') as selected_count
            FROM jobs j
            WHERE j.poster_id = ? AND j.status IN ('Available', 'Worker Selected', 'In Progress')
            ORDER BY j.created_at DESC
        """, (user_id,))
        my_active_posted_jobs = [dict(row) for row in cur.fetchall()]

    # Available jobs for quick browsing
    available_jobs = JobModel.get_all(status='Available')[:6]

    return render_template(
        'dashboard.html',
        user=user,
        posted_count=posted_count,
        apps_count=apps_count,
        active_worker_tasks=active_worker_tasks,
        pending_confirmations=pending_confirmations,
        my_active_posted_jobs=my_active_posted_jobs,
        available_jobs=available_jobs
    )
