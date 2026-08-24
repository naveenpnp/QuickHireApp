from flask import Blueprint, request, redirect, url_for, flash, render_template
from models import AssignmentModel, JobModel, UserModel, MessageModel, db_cursor
from services.auth_service import login_required, get_current_user
from services.payment_service import calculate_payment, parse_time_or_dt
from services.reliability_service import update_worker_on_completion, update_worker_on_noshow
from datetime import datetime

assignment_bp = Blueprint('assignment_routes', __name__)

@assignment_bp.route('/start-job/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def start_job(assignment_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.login'))

    assignment = AssignmentModel.get_by_id(assignment_id)
    if not assignment:
        flash("Assignment not found.", "danger")
        return redirect(url_for('job_routes.my_jobs'))

    # Rule 4: Only the selected worker can start the job
    if assignment['worker_id'] != user['id']:
        flash("Unauthorized action. You are not assigned to this job.", "danger")
        return redirect(url_for('job_routes.my_jobs'))

    if assignment['status'] != 'Assigned':
        flash(f"Job is already in '{assignment['status']}' state.", "info")
        return redirect(url_for('job_routes.job_details', job_id=assignment['job_id']))

    # Allow custom timestamp for simulation or default to current time
    simulated_start = request.form.get('custom_start_time') if request.method == 'POST' else None
    if simulated_start:
        try:
            start_dt = parse_time_or_dt(simulated_start, assignment['job_date'])
        except Exception:
            start_dt = datetime.now()
    else:
        start_dt = datetime.now()

    start_time_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")

    # Check if late compared to scheduled start
    try:
        sched_start_dt = parse_time_or_dt(assignment['start_time'], assignment['job_date'])
        is_late = 1 if (start_dt - sched_start_dt).total_seconds() > 180 else 0
    except Exception:
        is_late = 0

    with db_cursor(commit=True) as cur:
        cur.execute("""
            UPDATE job_assignments
            SET actual_start_time = ?, late = ?, status = 'In Progress'
            WHERE id = ?
        """, (start_time_str, is_late, assignment_id))

        cur.execute("UPDATE jobs SET status = 'In Progress' WHERE id = ?", (assignment['job_id'],))

    # Send in-app notification message to employer
    try:
        MessageModel.create(
            job_id=assignment['job_id'],
            sender_id=user['id'],
            receiver_id=assignment['poster_id'],
            message=f"🟢 WORK STARTED: I have clocked in for '{assignment['job_title']}' at {start_time_str}. The live stopwatch timer is active!"
        )
    except Exception:
        pass

    flash("Clock-in successful! Live Stopwatch Timer is now running. The employer has received a start notification.", "success")
    return redirect(url_for('job_routes.job_details', job_id=assignment['job_id']))

@assignment_bp.route('/complete-job/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def complete_job(assignment_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.login'))

    assignment = AssignmentModel.get_by_id(assignment_id)
    if not assignment:
        flash("Assignment not found.", "danger")
        return redirect(url_for('job_routes.my_jobs'))

    # Rule 4: Only assigned worker can mark complete
    if assignment['worker_id'] != user['id']:
        flash("Unauthorized action. You are not assigned to this job.", "danger")
        return redirect(url_for('job_routes.my_jobs'))

    # Rule 5: A worker must start before they can complete
    if assignment['status'] != 'In Progress' or not assignment['actual_start_time']:
        flash("You must start the job before you can mark it as complete.", "warning")
        return redirect(url_for('job_routes.job_details', job_id=assignment['job_id']))

    # Allow custom timestamp or simulation preset
    simulated_end = request.form.get('custom_end_time') if request.method == 'POST' else None
    if simulated_end:
        try:
            end_dt = parse_time_or_dt(simulated_end, assignment['job_date'])
        except Exception:
            end_dt = datetime.now()
    else:
        end_dt = datetime.now()

    end_time_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

    # Smart Payment Calculation (§7)
    calc_res = calculate_payment(
        scheduled_start=assignment['start_time'],
        scheduled_end=assignment['end_time'],
        actual_start=assignment['actual_start_time'],
        actual_end=end_time_str,
        payment_per_worker=assignment['scheduled_payment'],
        ref_date=assignment['job_date']
    )

    with db_cursor(commit=True) as cur:
        cur.execute("""
            UPDATE job_assignments
            SET actual_end_time = ?,
                scheduled_hours = ?,
                actual_hours = ?,
                calculated_payment = ?,
                late = ?,
                status = 'Awaiting Confirmation'
            WHERE id = ?
        """, (
            end_time_str,
            calc_res['scheduled_hours'],
            calc_res['actual_hours'],
            calc_res['calculated_payment'],
            1 if calc_res['late'] else 0,
            assignment_id
        ))

        cur.execute("UPDATE jobs SET status = 'Awaiting Confirmation' WHERE id = ?", (assignment['job_id'],))

    # Send in-app notification message to employer
    try:
        MessageModel.create(
            job_id=assignment['job_id'],
            sender_id=user['id'],
            receiver_id=assignment['poster_id'],
            message=f"✅ WORK COMPLETED: I have finished work for '{assignment['job_title']}'. Total hours: {calc_res['actual_hours']} hrs. Calculated pay: ₹{calc_res['calculated_payment']:.2f}. Please confirm to release payment."
        )
    except Exception:
        pass

    flash(f"Job marked complete! Hours: {calc_res['actual_hours']} hrs. Calculated Payout: ₹{calc_res['calculated_payment']:,.2f}. Employer has been notified to confirm and release funds.", "success")
    return redirect(url_for('job_routes.job_details', job_id=assignment['job_id']))

@assignment_bp.route('/confirm-job/<int:assignment_id>', methods=['POST'])
@login_required
def confirm_job(assignment_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.login'))

    assignment = AssignmentModel.get_by_id(assignment_id)
    if not assignment:
        flash("Assignment not found.", "danger")
        return redirect(url_for('job_routes.my_jobs'))

    # Check poster ownership
    if assignment['poster_id'] != user['id']:
        flash("Unauthorized action. Only the job poster can confirm completion.", "danger")
        return redirect(url_for('job_routes.job_details', job_id=assignment['job_id']))

    # Rule 6: Guard against paying twice
    if assignment['status'] != 'Awaiting Confirmation':
        flash(f"This assignment cannot be confirmed because its status is '{assignment['status']}'.", "warning")
        return redirect(url_for('job_routes.job_details', job_id=assignment['job_id']))

    calculated_pay = float(assignment['calculated_payment'] if assignment['calculated_payment'] is not None else assignment['scheduled_payment'])
    scheduled_pay = float(assignment['scheduled_payment'])
    refund_to_poster = round(scheduled_pay - calculated_pay, 2) if scheduled_pay > calculated_pay else 0.0

    worker_id = assignment['worker_id']
    job_id = assignment['job_id']
    poster_id = assignment['poster_id']
    is_late = bool(assignment['late'])

    # Rule 7: Atomic wallet and escrow transfer
    with db_cursor(commit=True) as cur:
        # 1. Update poster balances
        cur.execute("SELECT wallet_balance, secured_balance FROM users WHERE id = ?", (poster_id,))
        p_row = cur.fetchone()
        new_p_secured = max(0.0, round(p_row['secured_balance'] - scheduled_pay, 2))
        new_p_wallet = round(p_row['wallet_balance'] + refund_to_poster, 2)

        cur.execute("""
            UPDATE users SET wallet_balance = ?, secured_balance = ? WHERE id = ?
        """, (new_p_wallet, new_p_secured, poster_id))

        # 2. Update worker balance
        cur.execute("SELECT wallet_balance FROM users WHERE id = ?", (worker_id,))
        w_row = cur.fetchone()
        new_w_wallet = round(w_row['wallet_balance'] + calculated_pay, 2)
        cur.execute("UPDATE users SET wallet_balance = ? WHERE id = ?", (new_w_wallet, worker_id))

        # 3. Log Transactions
        cur.execute("""
            INSERT INTO transactions (user_id, job_id, amount, transaction_type, description)
            VALUES (?, ?, ?, 'Debit', ?)
        """, (poster_id, job_id, calculated_pay, f"Payment released to {assignment['worker_name']} for job: {assignment['job_title']}"))

        if refund_to_poster > 0:
            cur.execute("""
                INSERT INTO transactions (user_id, job_id, amount, transaction_type, description)
                VALUES (?, ?, ?, 'Credit', ?)
            """, (poster_id, job_id, refund_to_poster, f"Refund from unworked hours for job: {assignment['job_title']}"))

        cur.execute("""
            INSERT INTO transactions (user_id, job_id, amount, transaction_type, description)
            VALUES (?, ?, ?, 'Credit', ?)
        """, (worker_id, job_id, calculated_pay, f"Payment earned for completed job: {assignment['job_title']}"))

        # 4. Update assignment and application status
        cur.execute("UPDATE job_assignments SET status = 'Completed' WHERE id = ?", (assignment_id,))
        cur.execute("UPDATE applications SET status = 'Completed' WHERE job_id = ? AND worker_id = ?", (job_id, worker_id))

        # 5. Check if all required assignments for this job are completed
        cur.execute("""
            SELECT COUNT(*) FROM job_assignments WHERE job_id = ? AND status = 'Completed'
        """, (job_id,))
        completed_count = cur.fetchone()[0]

        if completed_count >= assignment['required_workers']:
            cur.execute("UPDATE jobs SET status = 'Completed' WHERE id = ?", (job_id,))

    # Send in-app notification message to worker
    try:
        MessageModel.create(
            job_id=job_id,
            sender_id=user['id'],
            receiver_id=worker_id,
            message=f"🎉 PAYMENT RELEASED: I have confirmed your work for '{assignment['job_title']}'. ₹{calculated_pay:.2f} has been transferred to your wallet!"
        )
    except Exception:
        pass

    # Rule 10 & 11: Update worker reliability and completed count
    update_worker_on_completion(worker_id, is_late=is_late)

    flash(f"Job completed and confirmed! ₹{calculated_pay:,.2f} transferred to {assignment['worker_name']}. Please leave a review.", "success")
    return redirect(url_for('review_routes.submit_review', job_id=job_id, user_id=worker_id))

@assignment_bp.route('/no-show/<int:assignment_id>', methods=['POST'])
@login_required
def no_show(assignment_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.login'))

    assignment = AssignmentModel.get_by_id(assignment_id)
    if not assignment:
        flash("Assignment not found.", "danger")
        return redirect(url_for('job_routes.my_jobs'))

    # Check poster ownership
    if assignment['poster_id'] != user['id']:
        flash("Unauthorized action. Only the job poster can mark a no-show.", "danger")
        return redirect(url_for('job_routes.job_details', job_id=assignment['job_id']))

    if assignment['status'] in ('Completed', 'No Show'):
        flash(f"Assignment is already marked as '{assignment['status']}'.", "warning")
        return redirect(url_for('job_routes.job_details', job_id=assignment['job_id']))

    worker_id = assignment['worker_id']
    job_id = assignment['job_id']

    # Rule 8: No payment to worker, payment stays secured in escrow for poster
    # Rule 9: Worker reliability -10, no_shows += 1
    with db_cursor(commit=True) as cur:
        cur.execute("UPDATE job_assignments SET no_show = 1, status = 'No Show' WHERE id = ?", (assignment_id,))
        cur.execute("UPDATE applications SET status = 'No Show' WHERE job_id = ? AND worker_id = ?", (job_id, worker_id))

        # Check remaining non-no-show assignments count
        cur.execute("""
            SELECT COUNT(*) FROM job_assignments
            WHERE job_id = ? AND status NOT IN ('No Show')
        """, (job_id,))
        active_assignments = cur.fetchone()[0]

        # Reopen job if needed
        if active_assignments < assignment['required_workers']:
            cur.execute("UPDATE jobs SET status = 'Available' WHERE id = ?", (job_id,))

    update_worker_on_noshow(worker_id)

    flash(f"Worker marked as No-Show. Worker reliability score penalized by 10. The job slot has been reopened.", "warning")
    return redirect(url_for('job_routes.job_details', job_id=job_id))
