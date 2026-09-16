@echo off
rem Start dnfm-auto keypress script (double-click to run)
chcp 65001 >nul
cd /d "%~dp0"
.venv\Scripts\python.exe main.py
pause
