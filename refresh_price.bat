@echo off
rem 独立功能：刷新商品价格（双击运行，请先把游戏切到神秘商店界面）
cd /d %~dp0
.\.venv\Scripts\python.exe tools\refresh_price.py
echo.
pause
