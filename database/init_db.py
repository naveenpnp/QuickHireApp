import sqlite3
import os
import sys

# Ensure database directory is in path
DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, 'quickhire.db')
SCHEMA_PATH = os.path.join(DB_DIR, 'schema.sql')

if DB_DIR not in sys.path:
    sys.path.insert(0, DB_DIR)

from seed import seed_database

def init_db(force=False):
    if force and os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception:
            pass

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check if tables already exist
    cursor.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='users'")
    table_exists = cursor.fetchone()[0] > 0

    if not table_exists or force:
        print("Executing schema.sql...")
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        cursor.executescript(schema_sql)
        conn.commit()
        print("Schema created.")

        print("Seeding database...")
        seed_database(conn)
        print("Database initialized and seeded.")
    else:
        # Schema migration check: ensure phone and role columns exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'phone' not in columns:
            print("Adding missing 'phone' column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT '+91 98765 43210'")
            conn.commit()
        if 'role' not in columns:
            print("Adding missing 'role' column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'worker'")
            conn.commit()

        # Ensure messages table exists
        cursor.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='messages'")
        if cursor.fetchone()[0] == 0:
            print("Creating missing 'messages' table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    sender_id INTEGER NOT NULL,
                    receiver_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
                    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            conn.commit()

        print("Database already initialized. Ensuring categories and demo users exist...")
        seed_database(conn)

    conn.close()
    print(f"QuickHire database ready at: {DB_PATH}")

if __name__ == '__main__':
    force_init = '--force' in sys.argv
    init_db(force=force_init)
