from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import JobModel, UserModel, ApplicationModel, AssignmentModel, TransactionModel, db_cursor
from services.auth_service import login_required, get_current_user
from datetime import datetime

job_bp = Blueprint('job_routes', __name__)

@job_bp.route('/jobs')
def jobs():
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    urgent_only = request.args.get('urgent') == '1'

    all_jobs = JobModel.get_all(search=search, category=category, urgent_only=urgent_only)

    with db_cursor() as cur:
        cur.execute("SELECT * FROM categories ORDER BY name ASC")
        categories = [dict(row) for row in cur.fetchall()]

    return render_template(
        'jobs.html',
        jobs=all_jobs,
        categories=categories,
        search=search,
        selected_category=category,
        urgent_only=urgent_only
    )

@job_bp.route('/job/<int:job_id>')
def job_details(job_id):
    job = JobModel.get_by_id(job_id)
    if not job:
        flash("Job not found.", "danger")
        return redirect(url_for('job_routes.jobs'))

    current_user = get_current_user()
    is_poster = current_user and (current_user['id'] == job['poster_id'])

    applicants = []
    assignments = []
    user_application = None
    user_assignment = None

    if is_poster:
        applicants = ApplicationModel.get_by_job(job_id)
        assignments = AssignmentModel.get_by_job(job_id)
    elif current_user:
        user_application = ApplicationModel.get_by_job_and_worker(job_id, current_user['id'])
        user_assignment = AssignmentModel.get_by_job_and_worker(job_id, current_user['id'])

    # Calculate exact scheduled shift duration
    try:
        from services.payment_service import parse_time_or_dt
        s_dt = parse_time_or_dt(job['start_time'], job['job_date'])
        e_dt = parse_time_or_dt(job['end_time'], job['job_date'])
        job_scheduled_seconds = int(max(60, (e_dt - s_dt).total_seconds()))
    except Exception:
        job_scheduled_seconds = 3600 * 3

    if job_scheduled_seconds < 3600:
        mins = max(1, int(job_scheduled_seconds // 60))
        job_scheduled_display = f"{mins} mins"
    else:
        hrs = round(job_scheduled_seconds / 3600.0, 1)
        job_scheduled_display = f"{hrs} hrs"

    return render_template(
        'job_details.html',
        job=job,
        is_poster=is_poster,
        applicants=applicants,
        assignments=assignments,
        user_application=user_application,
        user_assignment=user_assignment,
        job_scheduled_seconds=job_scheduled_seconds,
        job_scheduled_display=job_scheduled_display,
        current_user=current_user
    )

@job_bp.route('/post-job', methods=['GET', 'POST'])
@login_required
def post_job():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.login'))

    with db_cursor() as cur:
        cur.execute("SELECT * FROM categories ORDER BY name ASC")
        categories = [dict(row) for row in cur.fetchall()]

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        job_date = request.form.get('job_date', '').strip()
        start_time = request.form.get('start_time', '').strip()
        end_time = request.form.get('end_time', '').strip()
        required_workers_str = request.form.get('required_workers', '1').strip()
        payment_str = request.form.get('payment', '0').strip()
        urgent = 1 if request.form.get('urgent') else 0

        # Validate inputs
        if not (title and category and description and location and job_date and start_time and end_time):
            flash("Please fill in all required fields.", "danger")
            return render_template('post_job.html', categories=categories, form=request.form)

        try:
            required_workers = int(required_workers_str)
            payment = float(payment_str)
            if required_workers < 1:
                raise ValueError("Required workers must be at least 1.")
            if payment <= 0:
                raise ValueError("Payment amount must be positive.")
        except ValueError as e:
            flash(f"Invalid numeric input: {str(e)}", "danger")
            return render_template('post_job.html', categories=categories, form=request.form)

        total_escrow = payment * required_workers

        # Check wallet balance
        if user['wallet_balance'] < total_escrow:
            flash(f"Insufficient wallet balance. You need ₹{total_escrow:,.2f} (₹{payment:,.2f} × {required_workers} workers) but have ₹{user['wallet_balance']:,.2f}.", "danger")
            return render_template('post_job.html', categories=categories, form=request.form)

        # Atomic transaction: deduct wallet, increase secured_balance, create job, record transaction
        with db_cursor(commit=True) as cur:
            # Re-fetch user balance inside transaction
            cur.execute("SELECT wallet_balance, secured_balance FROM users WHERE id = ?", (user['id'],))
            u_row = cur.fetchone()
            if u_row['wallet_balance'] < total_escrow:
                flash("Insufficient wallet balance.", "danger")
                return render_template('post_job.html', categories=categories, form=request.form)

            new_wallet = round(u_row['wallet_balance'] - total_escrow, 2)
            new_secured = round(u_row['secured_balance'] + total_escrow, 2)

            cur.execute("""
                UPDATE users SET wallet_balance = ?, secured_balance = ? WHERE id = ?
            """, (new_wallet, new_secured, user['id']))

            # Create Job
            cur.execute("""
                INSERT INTO jobs (poster_id, title, category, description, location, job_date, start_time, end_time, required_workers, payment, urgent, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Available')
            """, (user['id'], title, category, description, location, job_date, start_time, end_time, required_workers, payment, urgent))
            job_id = cur.lastrowid

            # Create Transaction Record
            cur.execute("""
                INSERT INTO transactions (user_id, job_id, amount, transaction_type, description)
                VALUES (?, ?, ?, 'Debit', ?)
            """, (user['id'], job_id, total_escrow, f"Payment secured in escrow for: {title} ({required_workers} worker(s) @ ₹{payment})"))

        flash(f"Job posted successfully! ₹{total_escrow:,.2f} has been placed in secured escrow.", "success")
        return redirect(url_for('job_routes.job_details', job_id=job_id))

    return render_template('post_job.html', categories=categories, form={})

@job_bp.route('/my-jobs')
@login_required
def my_jobs():
    user = get_current_user()
    user_id = user['id']

    with db_cursor() as cur:
        # 1. Jobs I Posted
        cur.execute("""
            SELECT j.*,
                   (SELECT COUNT(*) FROM applications WHERE job_id = j.id) as applicant_count,
                   (SELECT COUNT(*) FROM job_assignments WHERE job_id = j.id AND status != 'No Show') as assigned_count
            FROM jobs j
            WHERE j.poster_id = ?
            ORDER BY j.created_at DESC
        """, (user_id,))
        posted_jobs = [dict(row) for row in cur.fetchall()]

        # 2. Jobs I Applied For
        cur.execute("""
            SELECT a.*, j.title as job_title, j.category as job_category, j.location as job_location,
                   j.job_date, j.start_time, j.end_time, j.payment as job_payment, j.urgent as job_urgent,
                   j.status as job_status, u.name as poster_name,
                   (SELECT id FROM job_assignments WHERE job_id = j.id AND worker_id = a.worker_id) as assignment_id
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            JOIN users u ON j.poster_id = u.id
            WHERE a.worker_id = ?
            ORDER BY a.applied_at DESC
        """, (user_id,))
        applied_jobs = [dict(row) for row in cur.fetchall()]

        # 3. Jobs I Am Working On (Assigned / In Progress / Awaiting Confirmation)
        cur.execute("""
            SELECT ja.*, j.title as job_title, j.category as job_category, j.location as job_location,
                   j.job_date, j.start_time, j.end_time, j.payment as job_payment, j.urgent as job_urgent,
                   u.name as poster_name, u.email as poster_email, u.is_online as poster_is_online
            FROM job_assignments ja
            JOIN jobs j ON ja.job_id = j.id
            JOIN users u ON j.poster_id = u.id
            WHERE ja.worker_id = ? AND ja.status IN ('Assigned', 'In Progress', 'Awaiting Confirmation')
            ORDER BY ja.id DESC
        """, (user_id,))
        working_jobs = [dict(row) for row in cur.fetchall()]

        # 4. Completed Jobs (Both posted by user and worked by user)
        cur.execute("""
            SELECT 'worked' as role, ja.id as assignment_id, ja.calculated_payment, ja.actual_hours,
                   ja.actual_start_time, ja.actual_end_time, ja.late,
                   j.id as job_id, j.title as job_title, j.category as job_category, j.location as job_location,
                   j.job_date, u.id as other_user_id, u.name as other_user_name,
                   (SELECT COUNT(*) FROM reviews WHERE job_id = j.id AND reviewer_id = ? AND reviewed_user_id = u.id) as has_reviewed
            FROM job_assignments ja
            JOIN jobs j ON ja.job_id = j.id
            JOIN users u ON j.poster_id = u.id
            WHERE ja.worker_id = ? AND ja.status = 'Completed'
            UNION ALL
            SELECT 'posted' as role, ja.id as assignment_id, ja.calculated_payment, ja.actual_hours,
                   ja.actual_start_time, ja.actual_end_time, ja.late,
                   j.id as job_id, j.title as job_title, j.category as job_category, j.location as job_location,
                   j.job_date, u.id as other_user_id, u.name as other_user_name,
                   (SELECT COUNT(*) FROM reviews WHERE job_id = j.id AND reviewer_id = ? AND reviewed_user_id = u.id) as has_reviewed
            FROM job_assignments ja
            JOIN jobs j ON ja.job_id = j.id
            JOIN users u ON ja.worker_id = u.id
            WHERE j.poster_id = ? AND ja.status = 'Completed'
            ORDER BY job_date DESC
        """, (user_id, user_id, user_id, user_id))
        completed_jobs = [dict(row) for row in cur.fetchall()]

    default_tab = 'posted' if session.get('role', 'worker') == 'employer' else 'working'
    active_tab = request.args.get('tab', default_tab)
    return render_template(
        'my_jobs.html',
        posted_jobs=posted_jobs,
        applied_jobs=applied_jobs,
        working_jobs=working_jobs,
        completed_jobs=completed_jobs,
        active_tab=active_tab
    )

@job_bp.route('/api/job-status/<int:job_id>')
def api_job_status(job_id):
    job = JobModel.get_by_id(job_id)
    if not job:
        return {"error": "Job not found"}, 404

    current_user = get_current_user()
    is_poster = current_user and (current_user['id'] == job['poster_id'])
    
    user_assignment = None
    user_application = None
    if current_user:
        user_assignment = AssignmentModel.get_by_job_and_worker(job_id, current_user['id'])
        user_application = ApplicationModel.get_by_job_and_worker(job_id, current_user['id'])

    assignments = AssignmentModel.get_by_job(job_id) if is_poster else []
    applicants = ApplicationModel.get_by_job(job_id) if is_poster else []

    return {
        "job_id": job_id,
        "job_status": job['status'],
        "is_poster": is_poster,
        "user_role": current_user.get('role', 'worker') if current_user else 'guest',
        "user_assignment_status": user_assignment['status'] if user_assignment else None,
        "user_application_status": user_application['status'] if user_application else None,
        "actual_start_time": user_assignment['actual_start_time'] if user_assignment else None,
        "actual_end_time": user_assignment['actual_end_time'] if user_assignment else None,
        "calculated_payment": user_assignment['calculated_payment'] if user_assignment else None,
        "applicants_count": len(applicants),
        "assignments_count": len(assignments),
        "assigned_statuses": [a['status'] for a in assignments]
    }
