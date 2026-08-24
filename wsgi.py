import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_ROOT, 'backend')
DATABASE_DIR = os.path.join(PROJECT_ROOT, 'database')

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if DATABASE_DIR not in sys.path:
    sys.path.insert(0, DATABASE_DIR)

from app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
