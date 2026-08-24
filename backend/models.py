import sqlite3
import os
from contextlib import contextmanager

# Path to database relative to this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', 'database', 'quickhire.db'))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def db_cursor(commit=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

class UserModel:
    @staticmethod
    def get_by_id(user_id):
        with db_cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_email(email):
        with db_cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def create(name, email, password_hash, location="", skills="", phone="+91 98765 43210", role="worker"):
        with db_cursor(commit=True) as cur:
            cur.execute("""
                INSERT INTO users (name, email, password, location, skills, phone, role, wallet_balance, secured_balance, rating, reliability_score, completed_jobs, late_arrivals, no_shows, is_online)
                VALUES (?, ?, ?, ?, ?, ?, ?, 5000.0, 0.0, NULL, 100, 0, 0, 0, 0)
            """, (name.strip(), email.strip().lower(), password_hash, location.strip(), skills.strip(), phone.strip() if phone else '+91 98765 43210', role.strip().lower() if role else 'worker'))
            return cur.lastrowid

    @staticmethod
    def update_online_status(user_id, is_online):
        with db_cursor(commit=True) as cur:
            cur.execute("UPDATE users SET is_online = ? WHERE id = ?", (1 if is_online else 0, user_id))

    @staticmethod
    def update_profile(user_id, name, location, skills, phone="+91 98765 43210"):
        with db_cursor(commit=True) as cur:
            cur.execute("""
                UPDATE users SET name = ?, location = ?, skills = ?, phone = ? WHERE id = ?
            """, (name.strip(), location.strip(), skills.strip(), phone.strip() if phone else '+91 98765 43210', user_id))

    @staticmethod
    def update_password(email, password_hash):
        with db_cursor(commit=True) as cur:
            cur.execute("UPDATE users SET password = ? WHERE email = ?", (password_hash, email.strip().lower()))

class JobModel:
    @staticmethod
    def get_all(search=None, category=None, urgent_only=False, status=None):
        query = """
            SELECT j.*, u.name as poster_name, u.location as poster_location, u.phone as poster_phone,
                   u.rating as poster_rating, u.reliability_score as poster_reliability, u.is_online as poster_is_online,
                   (SELECT COUNT(*) FROM applications WHERE job_id = j.id) as applicant_count,
                   (SELECT COUNT(*) FROM job_assignments WHERE job_id = j.id) as assigned_count
            FROM jobs j
            JOIN users u ON j.poster_id = u.id
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND j.status = ?"
            params.append(status)
        if search:
            query += " AND (j.title LIKE ? OR j.location LIKE ? OR j.description LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term])
        if category and category != 'All':
            query += " AND j.category = ?"
            params.append(category)
        if urgent_only:
            query += " AND j.urgent = 1"

        query += " ORDER BY j.urgent DESC, j.created_at DESC"

        with db_cursor() as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def get_by_id(job_id):
        query = """
            SELECT j.*, u.name as poster_name, u.email as poster_email, u.phone as poster_phone, u.location as poster_location,
                   u.rating as poster_rating, u.reliability_score as poster_reliability, u.is_online as poster_is_online,
                   (SELECT COUNT(*) FROM applications WHERE job_id = j.id) as applicant_count,
                   (SELECT COUNT(*) FROM job_assignments WHERE job_id = j.id) as assigned_count
            FROM jobs j
            JOIN users u ON j.poster_id = u.id
            WHERE j.id = ?
        """
        with db_cursor() as cur:
            cur.execute(query, (job_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def create(poster_id, title, category, description, location, job_date, start_time, end_time, required_workers, payment, urgent):
        with db_cursor(commit=True) as cur:
            cur.execute("""
                INSERT INTO jobs (poster_id, title, category, description, location, job_date, start_time, end_time, required_workers, payment, urgent, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Available')
            """, (poster_id, title, category, description, location, job_date, start_time, end_time, required_workers, payment, 1 if urgent else 0))
            return cur.lastrowid

    @staticmethod
    def update_status(job_id, status):
        with db_cursor(commit=True) as cur:
            cur.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))

class ApplicationModel:
    @staticmethod
    def get_by_job(job_id):
        query = """
            SELECT a.*, u.name as worker_name, u.email as worker_email, u.phone as worker_phone, u.location as worker_location,
                   u.skills as worker_skills, u.rating as worker_rating, u.reliability_score as worker_reliability,
                   u.completed_jobs as worker_completed_jobs, u.late_arrivals as worker_late_arrivals,
                   u.no_shows as worker_no_shows, u.is_online as worker_is_online
            FROM applications a
            JOIN users u ON a.worker_id = u.id
            WHERE a.job_id = ?
            ORDER BY u.reliability_score DESC, a.applied_at ASC
        """
        with db_cursor() as cur:
            cur.execute(query, (job_id,))
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def get_by_worker(worker_id):
        query = """
            SELECT a.*, j.title as job_title, j.category as job_category, j.location as job_location,
                   j.job_date, j.start_time, j.end_time, j.payment as job_payment, j.urgent as job_urgent,
                   j.status as job_status, u.name as poster_name, u.phone as poster_phone,
                   (SELECT id FROM job_assignments WHERE job_id = j.id AND worker_id = a.worker_id) as assignment_id
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            JOIN users u ON j.poster_id = u.id
            WHERE a.worker_id = ?
            ORDER BY a.applied_at DESC
        """
        with db_cursor() as cur:
            cur.execute(query, (worker_id,))
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def get_by_job_and_worker(job_id, worker_id):
        with db_cursor() as cur:
            cur.execute("SELECT * FROM applications WHERE job_id = ? AND worker_id = ?", (job_id, worker_id))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_id(app_id):
        with db_cursor() as cur:
            cur.execute("SELECT * FROM applications WHERE id = ?", (app_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def create(job_id, worker_id):
        with db_cursor(commit=True) as cur:
            cur.execute("""
                INSERT INTO applications (job_id, worker_id, status)
                VALUES (?, ?, 'Applied')
            """, (job_id, worker_id))
            return cur.lastrowid

class AssignmentModel:
    @staticmethod
    def get_by_id(assignment_id):
        query = """
            SELECT ja.*, j.title as job_title, j.poster_id, j.category as job_category, j.location as job_location,
                   j.job_date, j.start_time, j.end_time, j.payment as scheduled_payment, j.urgent as job_urgent,
                   j.status as job_status, j.required_workers,
                   poster.name as poster_name, poster.email as poster_email, poster.phone as poster_phone,
                   worker.name as worker_name, worker.email as worker_email, worker.phone as worker_phone, worker.reliability_score as worker_reliability
            FROM job_assignments ja
            JOIN jobs j ON ja.job_id = j.id
            JOIN users poster ON j.poster_id = poster.id
            JOIN users worker ON ja.worker_id = worker.id
            WHERE ja.id = ?
        """
        with db_cursor() as cur:
            cur.execute(query, (assignment_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_job_and_worker(job_id, worker_id):
        with db_cursor() as cur:
            cur.execute("SELECT * FROM job_assignments WHERE job_id = ? AND worker_id = ?", (job_id, worker_id))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_job(job_id):
        query = """
            SELECT ja.*, u.name as worker_name, u.email as worker_email, u.phone as worker_phone, u.reliability_score as worker_reliability,
                   u.rating as worker_rating, u.is_online as worker_is_online
            FROM job_assignments ja
            JOIN users u ON ja.worker_id = u.id
            WHERE ja.job_id = ?
        """
        with db_cursor() as cur:
            cur.execute(query, (job_id,))
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def get_active_in_progress_by_user(user_id):
        """Returns any active 'In Progress' assignment for the user (as worker or poster)."""
        query = """
            SELECT ja.*, j.title as job_title, j.poster_id, j.category as job_category, j.location as job_location,
                   j.job_date, j.start_time, j.end_time, j.payment as scheduled_payment,
                   poster.name as poster_name, poster.phone as poster_phone,
                   worker.name as worker_name, worker.phone as worker_phone
            FROM job_assignments ja
            JOIN jobs j ON ja.job_id = j.id
            JOIN users poster ON j.poster_id = poster.id
            JOIN users worker ON ja.worker_id = worker.id
            WHERE (ja.worker_id = ? OR j.poster_id = ?) AND ja.status = 'In Progress'
            ORDER BY ja.actual_start_time DESC LIMIT 1
        """
        with db_cursor() as cur:
            cur.execute(query, (user_id, user_id))
            row = cur.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_awaiting_confirmation_by_user(user_id):
        """Returns any active 'Awaiting Confirmation' assignment for the user (as worker or poster)."""
        query = """
            SELECT ja.*, j.title as job_title, j.poster_id, j.category as job_category, j.location as job_location,
                   j.job_date, j.start_time, j.end_time, j.payment as scheduled_payment,
                   poster.name as poster_name, poster.phone as poster_phone,
                   worker.name as worker_name, worker.phone as worker_phone
            FROM job_assignments ja
            JOIN jobs j ON ja.job_id = j.id
            JOIN users poster ON j.poster_id = poster.id
            JOIN users worker ON ja.worker_id = worker.id
            WHERE (ja.worker_id = ? OR j.poster_id = ?) AND ja.status = 'Awaiting Confirmation'
            ORDER BY ja.id DESC LIMIT 1
        """
        with db_cursor() as cur:
            cur.execute(query, (user_id, user_id))
            row = cur.fetchone()
            return dict(row) if row else None

class TransactionModel:
    @staticmethod
    def get_by_user(user_id):
        with db_cursor() as cur:
            cur.execute("""
                SELECT t.*, j.title as job_title
                FROM transactions t
                LEFT JOIN jobs j ON t.job_id = j.id
                WHERE t.user_id = ?
                ORDER BY t.created_at DESC
            """, (user_id,))
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def create(user_id, job_id, amount, transaction_type, description):
        with db_cursor(commit=True) as cur:
            cur.execute("""
                INSERT INTO transactions (user_id, job_id, amount, transaction_type, description)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, job_id, amount, transaction_type, description))
            return cur.lastrowid

class ReviewModel:
    @staticmethod
    def get_by_reviewed_user(user_id):
        query = """
            SELECT r.*, reviewer.name as reviewer_name, reviewer.rating as reviewer_rating,
                   j.title as job_title, j.category as job_category
            FROM reviews r
            JOIN users reviewer ON r.reviewer_id = reviewer.id
            JOIN jobs j ON r.job_id = j.id
            WHERE r.reviewed_user_id = ?
            ORDER BY r.created_at DESC
        """
        with db_cursor() as cur:
            cur.execute(query, (user_id,))
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def has_reviewed(job_id, reviewer_id, reviewed_user_id):
        with db_cursor() as cur:
            cur.execute("""
                SELECT id FROM reviews WHERE job_id = ? AND reviewer_id = ? AND reviewed_user_id = ?
            """, (job_id, reviewer_id, reviewed_user_id))
            return cur.fetchone() is not None

    @staticmethod
    def create(job_id, reviewer_id, reviewed_user_id, rating, review_text=""):
        with db_cursor(commit=True) as cur:
            cur.execute("""
                INSERT INTO reviews (job_id, reviewer_id, reviewed_user_id, rating, review)
                VALUES (?, ?, ?, ?, ?)
            """, (job_id, reviewer_id, reviewed_user_id, int(rating), review_text.strip() if review_text else None))
            return cur.lastrowid

class MessageModel:
    @staticmethod
    def get_conversation(job_id, user1_id, user2_id):
        query = """
            SELECT m.*, sender.name as sender_name, receiver.name as receiver_name
            FROM messages m
            JOIN users sender ON m.sender_id = sender.id
            JOIN users receiver ON m.receiver_id = receiver.id
            WHERE m.job_id = ?
              AND ((m.sender_id = ? AND m.receiver_id = ?) OR (m.sender_id = ? AND m.receiver_id = ?))
            ORDER BY m.created_at ASC
        """
        with db_cursor() as cur:
            cur.execute(query, (job_id, user1_id, user2_id, user2_id, user1_id))
            return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def create(job_id, sender_id, receiver_id, message):
        with db_cursor(commit=True) as cur:
            cur.execute("""
                INSERT INTO messages (job_id, sender_id, receiver_id, message)
                VALUES (?, ?, ?, ?)
            """, (job_id, sender_id, receiver_id, message.strip()))
            return cur.lastrowid

    @staticmethod
    def get_user_inbox(user_id):
        query = """
            SELECT m.*, j.title as job_title,
                   sender.name as sender_name, sender.phone as sender_phone,
                   receiver.name as receiver_name, receiver.phone as receiver_phone
            FROM messages m
            JOIN jobs j ON m.job_id = j.id
            JOIN users sender ON m.sender_id = sender.id
            JOIN users receiver ON m.receiver_id = receiver.id
            WHERE m.sender_id = ? OR m.receiver_id = ?
            ORDER BY m.created_at DESC
        """
        with db_cursor() as cur:
            cur.execute(query, (user_id, user_id))
            return [dict(row) for row in cur.fetchall()]
