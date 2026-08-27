import sqlite3
import os
import sys

# Ensure database directory is in path
DB_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(DB_DIR, 'schema.sql')

def get_db_path():
    if os.environ.get('VERCEL') == '1' or (os.path.exists(DB_DIR) and not os.access(DB_DIR, os.W_OK)):
        tmp_db = '/tmp/quickhire.db'
        orig_db = os.path.join(DB_DIR, 'quickhire.db')
        if not os.path.exists(tmp_db) and os.path.exists(orig_db):
            import shutil
            try:
                shutil.copy2(orig_db, tmp_db)
            except Exception:
                pass
        return tmp_db
    return os.path.join(DB_DIR, 'quickhire.db')

DB_PATH = get_db_path()

def _load_env():
    project_root = os.path.abspath(os.path.join(DB_DIR, '..'))
    env_file = os.path.join(project_root, '.env')
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_env()

try:
    from turso_adapter import get_turso_connection
except ImportError:
    def get_turso_connection():
        return None

from seed import seed_database

def init_db(force=False):
    turso_conn = get_turso_connection()
    if turso_conn:
        conn = turso_conn
        print("Connected to Turso Cloud Database.")
    else:
        db_file = get_db_path()
        if force and os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass
        conn = sqlite3.connect(db_file)

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
