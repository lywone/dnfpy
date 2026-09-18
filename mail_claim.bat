@echo off
rem 独立功能：邮件领取（双击运行，请先把游戏切到城镇主界面）
cd /d %~dp0
.\.venv\Scripts\python.exe mail_claim.py
echo.
pause
