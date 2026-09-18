@echo off
cd /d %~dp0
echo ============================================
echo   DNF 起源 自动过图挂机（auto_run.py）
echo ============================================
echo 1. 按 → 前进 2~3 秒，同时 ↑/↓ 交替移动约 20 秒
echo 2. 检测「再次挑战」按钮，没有则前进 2 秒再检测
echo 3. 检测到后按 F10，3 秒后复查，直到按钮消失进入下一轮
echo --------------------------------------------
echo 需准备：游戏已打开主城/副本、ADB 已连接、
echo         模板 templates\template_challenge.png
echo 制作模板：运行 auto_run.py --capture 截图，
echo         裁剪「再次挑战」按钮另存为 templates\template_challenge.png
echo --------------------------------------------
set PY=.venv\Scripts\python.exe
if not exist "%PY%" set PY=python
"%PY%" auto_run.py %*
echo.
pause
