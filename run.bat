@echo off
echo Starting Katilo ERP System...

:: Activate virtual environment if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment not found. Make sure you have created it with 'python -m venv venv'
    pause
    exit /b 1
)

:: Try to find an available port
set PORT=0
echo Attempting to start server on an available port...

:: Run the WSGI server
python wsgi.py

if errorlevel 1 (
    echo.
    echo Failed to start server. Trying alternative port...
    set PORT=5000
    python wsgi.py
)

if errorlevel 1 (
    echo.
    echo Failed to start server on alternative port.
    echo Please try running with a different port manually:
    echo set PORT=XXXX ^&^& python wsgi.py
    pause
    exit /b 1
)

:: Deactivate virtual environment
call deactivate
