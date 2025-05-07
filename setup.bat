@echo off
setlocal

echo === KATILO-ERP SETUP ===
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed.
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    pause
    exit /b
)

REM Get Python version
for /f "tokens=2 delims= " %%a in ('python --version') do set PY_VER=%%a
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set MAJOR=%%a
    set MINOR=%%b
)

REM Require Python >= 3.8
if %MAJOR% LSS 3 (
    echo Python version must be at least 3.8. Found: %PY_VER%
    pause
    exit /b
)
if %MAJOR%==3 if %MINOR% LSS 8 (
    echo Python version must be at least 3.8. Found: %PY_VER%
    pause
    exit /b
)

echo Detected Python version: %PY_VER%
echo.

REM Detect OS
ver | findstr /i "windows" >nul && (
    echo Operating System: Windows
) || (
    echo Operating System: Unknown or non-Windows (use shell script for Linux/macOS)
)

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install Flask and dependencies
echo Installing Flask and required extensions...
pip install flask flask-migrate flask-sqlalchemy

REM Install from requirements.txt if it exists
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
