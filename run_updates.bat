@echo off
echo ==========================================
echo   Disability Schemes Chatbot - Auto-Update
echo ==========================================
echo.
echo This will scrape official sources and update the chatbot's brain.
echo.

if not exist "venv\" (
    echo Error: venv directory not found! 
    echo Please make sure you are running this from the project root.
    pause
    exit /b
)

echo Starting update process...
.\venv\Scripts\python scripts/update_all.py

echo.
echo Done! You can now restart your chatbot to see the latest information.
pause
