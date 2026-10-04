@echo off
title Data Cleaning & Reporting Automation
cd /d "%~dp0"
echo ========================================================
echo   Launching Data Cleaning & Reporting Automation Web UI
echo ========================================================
echo.
python -m streamlit run app.py
pause
