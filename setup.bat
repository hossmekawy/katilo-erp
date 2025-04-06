@echo off
echo === KATILO-ERP SETUP ===
echo.

echo Creating virtual environment...
python -m venv venv

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing Flask and required extensions...
pip install flask
pip install flask-migrate
pip install flask-sqlalchemy

echo Installing all requirements (if requirements.txt exists)...
if exist requirements.txt (
    pip install -r requirements.txt
)

echo.
echo === SETUP COMPLETE ===
echo.
echo To run the application:
echo 1. Run "run.bat"
echo.
pause
