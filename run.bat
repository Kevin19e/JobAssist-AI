@echo off
echo Starting AI Job Assistant...
echo Please ensure you have an internet connection.
echo The application will open in your default browser.
echo.

:: Start the application in the virtual environment
start "" "http://127.0.0.1:8000"
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

pause
