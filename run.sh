#!/usr/bin/env bash
# QuickHire Automated Local Setup and Runner

set -e

echo "========================================="
echo "   QuickHire - Hyperlocal Work & Hire    "
echo "========================================="

# 1. Virtual environment setup
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv || python -m venv venv
fi

# 2. Activate venv
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
fi

# 3. Install requirements
echo "Installing backend requirements..."
pip install -r backend/requirements.txt

# 4. Initialize database
echo "Initializing SQLite database..."
python database/init_db.py

# 5. Run backend Flask app
echo "Starting QuickHire Web Server at http://127.0.0.1:5000..."
python backend/app.py
