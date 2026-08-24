@echo off
REM QuickHire Windows Automated Setup and Runner
echo =========================================
echo    QuickHire - Hyperlocal Work & Hire
echo =========================================

IF NOT EXIST "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing backend dependencies...
pip install -r backend\requirements.txt

echo Initializing database...
python database\init_db.py

echo Starting QuickHire application at http://127.0.0.1:5000 ...
python backend\app.py
pause
