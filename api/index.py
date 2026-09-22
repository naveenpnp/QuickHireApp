import os
import sys

# Ensure VERCEL env flag is active
os.environ['VERCEL'] = '1'
if not os.environ.get('SECRET_KEY', '').strip():
    os.environ['SECRET_KEY'] = 'quickhire-production-secret-key-2026-vault-auth-99x7'

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(PROJECT_ROOT, 'backend')
DATABASE_DIR = os.path.join(PROJECT_ROOT, 'database')

for path in [PROJECT_ROOT, BACKEND_DIR, DATABASE_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

from app import app
