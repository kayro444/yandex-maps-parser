@echo off
echo ========================================
echo   B2B Lead Parser — Web App
echo ========================================
call "%~dp0.venv\Scripts\activate.bat"
streamlit run "%~dp0app.py"
pause
