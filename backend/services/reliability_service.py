from models import db_cursor

def update_worker_on_completion(worker_id, is_late=False):
    """
    On confirmed completion:
    - completed_jobs += 1
    - reliability_score += 1 (cap at 100)
    - If is_late: late_arrivals += 1, reliability_score -= 2 (floor at 0)
    """
    with db_cursor(commit=True) as cur:
        cur.execute("SELECT reliability_score, completed_jobs, late_arrivals FROM users WHERE id = ?", (worker_id,))
        row = cur.fetchone()
        if not row:
            return

        current_score = row['reliability_score'] or 100
        completed = row['completed_jobs'] or 0
        lates = row['late_arrivals'] or 0

        completed += 1
        if is_late:
            lates += 1
            # Completion reward (+1) and late arrival penalty (-2)
            new_score = max(0, min(100, current_score + 1 - 2))
        else:
            new_score = min(100, current_score + 1)

        cur.execute("""
            UPDATE users
            SET reliability_score = ?, completed_jobs = ?, late_arrivals = ?
            WHERE id = ?
        """, (new_score, completed, lates, worker_id))

def update_worker_on_noshow(worker_id):
    """
    On worker no-show:
    - no_shows += 1
    - reliability_score -= 10 (floor at 0)
    """
    with db_cursor(commit=True) as cur:
        cur.execute("SELECT reliability_score, no_shows FROM users WHERE id = ?", (worker_id,))
        row = cur.fetchone()
        if not row:
            return

        current_score = row['reliability_score'] or 100
        no_shows = row['no_shows'] or 0

        new_score = max(0, current_score - 10)
        no_shows += 1

        cur.execute("""
            UPDATE users
            SET reliability_score = ?, no_shows = ?
            WHERE id = ?
        """, (new_score, no_shows, worker_id))

def recalculate_user_rating(user_id):
    """
    Recalculates mean rating from reviews received by user and updates users.rating.
    """
    with db_cursor(commit=True) as cur:
        cur.execute("""
            SELECT AVG(rating) as avg_rating, COUNT(rating) as total_reviews
            FROM reviews
            WHERE reviewed_user_id = ?
        """, (user_id,))
        row = cur.fetchone()
        if row and row['total_reviews'] > 0:
            avg_rating = round(row['avg_rating'], 1)
        else:
            avg_rating = None

        cur.execute("UPDATE users SET rating = ? WHERE id = ?", (avg_rating, user_id))
        return avg_rating
