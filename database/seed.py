import sqlite3
import os
from werkzeug.security import generate_password_hash
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quickhire.db')

CATEGORIES = [
    ('Event Work', 'bi-calendar-event'),
    ('Delivery', 'bi-truck'),
    ('Data Entry', 'bi-laptop'),
    ('Shop Assistant', 'bi-shop'),
    ('Restaurant Helper', 'bi-cup-hot'),
    ('College Work', 'bi-mortarboard'),
    ('Photography Assistant', 'bi-camera'),
    ('Marketing', 'bi-megaphone'),
    ('Office Assistant', 'bi-building'),
    ('Other', 'bi-grid')
]

def seed_database(conn=None):
    close_after = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        close_after = True

    cursor = conn.cursor()

    # 1. Seed Categories if empty
    cursor.execute("SELECT COUNT(*) FROM categories")
    cat_count = cursor.fetchone()[0]
    if cat_count == 0:
        for name, icon in CATEGORIES:
            cursor.execute(
                "INSERT OR IGNORE INTO categories (name, icon) VALUES (?, ?)",
                (name, icon)
            )

    # 2. Seed Users if not existing
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    pwd_hash = generate_password_hash("123456")

    if user_count == 0:
        cursor.execute("""
            INSERT OR IGNORE INTO users (name, email, password, skills, location, phone, role, wallet_balance, secured_balance, rating, reliability_score, completed_jobs, late_arrivals, no_shows, is_online)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Arun Kumar", "arun@gmail.com", pwd_hash, "Event Management, Photography, Logistics", "Trichy", "+91 98401 23456", "employer", 5000.0, 0.0, None, 100, 0, 0, 0, 0))

        cursor.execute("""
            INSERT OR IGNORE INTO users (name, email, password, skills, location, phone, role, wallet_balance, secured_balance, rating, reliability_score, completed_jobs, late_arrivals, no_shows, is_online)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("Rahul Sharma", "rahul@gmail.com", pwd_hash, "Data Entry, Delivery, Customer Support", "Chennai", "+91 97902 34567", "worker", 5000.0, 0.0, None, 100, 0, 0, 0, 0))

    # Retrieve user ids
    cursor.execute("SELECT id, email FROM users WHERE email IN ('arun@gmail.com', 'rahul@gmail.com')")
    users = {row[1]: row[0] for row in cursor.fetchall()}
    arun_id = users.get("arun@gmail.com")
    rahul_id = users.get("rahul@gmail.com")

    # 3. Seed Demo Jobs if not already seeded
    cursor.execute("SELECT COUNT(*) FROM jobs")
    job_count = cursor.fetchone()[0]

    # Update all demo jobs to belong to Employer Arun
    if arun_id and rahul_id:
        cursor.execute("UPDATE jobs SET poster_id = ? WHERE poster_id = ?", (arun_id, rahul_id))

    today_str = date.today().strftime("%Y-%m-%d")

    if job_count == 0 and arun_id:
        demo_jobs = [
            (
                arun_id,
                "Event Assistant for College Cultural Fest",
                "Event Work",
                "Need 1 dynamic student/worker to assist with stage coordination, guest reception, and kit distribution during our annual inter-college cultural fest.",
                "Trichy",
                today_str,
                "10:00",
                "16:00",
                1,
                900.0,
                1, # Urgent
                "Available"
            ),
            (
                arun_id,
                "Data Entry Assistant (Excel & Forms)",
                "Data Entry",
                "Assisting with digital catalog entry, spreadsheet verification, and customer order records update.",
                "Chennai",
                today_str,
                "09:00",
                "13:00",
                1,
                600.0,
                0, # Not urgent
                "Available"
            ),
            (
                arun_id,
                "Shop Helper & Inventory Stacking",
                "Shop Assistant",
                "Assist our retail clothing store staff with unpacking new inventory shipments, sorting garments by size, and organizing trial rooms.",
                "Coimbatore",
                today_str,
                "17:00",
                "21:00",
                2,
                500.0,
                0,
                "Available"
            ),
            (
                arun_id,
                "Delivery Assistant for Local Parcel Express",
                "Delivery",
                "Help delivery driver with parcel sorting, customer phone confirmations, and handoffs in Trichy city center.",
                "Trichy",
                today_str,
                "11:00",
                "15:00",
                1,
                700.0,
                1, # Urgent
                "Available"
            ),
        ]

        for job in demo_jobs:
            cursor.execute("""
                INSERT INTO jobs (poster_id, title, category, description, location, job_date, start_time, end_time, required_workers, payment, urgent, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, job)

    conn.commit()
    if close_after:
        conn.close()
    print("Database seeding completed successfully.")

if __name__ == '__main__':
    seed_database()
