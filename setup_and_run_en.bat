@echo off
echo Welcome! Setting up and running Katilo ERP...
echo.

echo 1. Creating virtual environment...
python -m venv venv
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to create virtual environment. Ensure Python is installed.
    pause
    exit /b %ERRORLEVEL%
)
echo Virtual environment created successfully!
echo.

echo 2. Activating virtual environment...
call venv\Scripts\activate
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to activate virtual environment.
    pause
    exit /b %ERRORLEVEL%
)
echo Virtual environment activated!
echo.

echo 3. Installing requirements from requirements.txt...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to install requirements. Ensure requirements.txt exists and internet is connected.
    pause
    exit /b %ERRORLEVEL%
)
echo Requirements installed successfully!
echo.

echo 4. Running the application...
python app.py
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to run app.py. Ensure the file exists and is valid.
    pause
    exit /b %ERRORLEVEL%
)

echo The application is now running! Open your browser at http://localhost:5000
pause
