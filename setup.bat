@echo off
color 0A
title KATILO ERP Setup & Launch

echo.
echo ===============================================================================
echo          Welcome to KATILO ERP - Version 1.0.0
echo ===============================================================================
echo.
echo      K - Knowledgeable Inventory Management
echo      A - Advanced Warehouse Solutions
echo      T - Transaction Tracking Excellence
echo      I - Intuitive User Experience
echo      L - Logistics Made Simple
echo      O - Optimized for Efficiency
echo.
echo Developed by 7AMLA TEAM  - GitHub: https://github.com/hossmekawy/katilo-erp
echo Logo: https://ik.imagekit.io/tijarahub/optimized/Frontend-Ayehia/Vendors/Egypt/Katilo/Logo.png
echo.
echo Preparing to set up and launch your ERP system...
timeout /t 2 >nul

echo.
echo [----------] 0%% Initializing...
timeout /t 1 >nul
cls

echo ===============================================================================
echo          Step 1: Creating Virtual Environment
echo ===============================================================================
echo.
echo [####------] 40%% Setting up venv...
python -m venv venv
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo ERROR: Failed to create virtual environment!
    echo Please ensure Python is installed and added to PATH.
    pause
    exit /b %ERRORLEVEL%
)
echo [#####-----] 50%% Virtual environment created successfully!
timeout /t 5 >nul
cls

echo ===============================================================================
echo          Step 2: Activating Virtual Environment
echo ===============================================================================
echo.
echo [######----] 60%% Activating...
call venv\Scripts\activate
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo ERROR: Failed to activate virtual environment!
    pause
    exit /b %ERRORLEVEL%
)
echo [#######---] 70%% Virtual environment activated!
timeout /t 5 >nul
cls

echo ===============================================================================
echo          Step 3: Installing Dependencies
echo ===============================================================================
echo.
echo [########--] 80%% Installing requirements...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo ERROR: Failed to install requirements!
    echo Ensure requirements.txt exists and you have an internet connection.
    pause
    exit /b %ERRORLEVEL%
)
echo [#########-] 90%% Requirements installed successfully!
timeout /t 5 >nul
cls

echo ===============================================================================
echo          Step 4: Launching KATILO ERP
echo ===============================================================================
echo.
echo [##########] 100%% Starting application...
timeout /t 1 >nul
python app.py
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo ERROR: Failed to run app.py!
    echo Ensure app.py exists and is valid.
    pause
    exit /b %ERRORLEVEL%
)

color 0A
echo.
echo ===============================================================================
echo          KATILO ERP is now running!
echo          Open your browser at: http://localhost:5000
echo ===============================================================================
echo.
echo Enjoy managing your inventory with KATILO ERP!
pause