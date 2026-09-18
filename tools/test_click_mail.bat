@echo off
cd /d D:\code\dnfm-auto
echo ============================================
echo   测试点击「邮箱」图标（test_click_mail.py）
echo ============================================
echo 1. 连接模拟器 ADB，截取 HDMI 完整游戏画面
echo 2. 用 test_icon.png 模板定位邮箱图标
echo 3. 触摸点击 + 验证已进入邮箱界面
echo 4. 点击完成给出提示音 + 弹窗
echo --------------------------------------------
echo 请确保：模拟器已启动、游戏在主城界面
echo 主城右下角应显示：邮箱/社交/角色/打造/冒险/背包
echo.
.venv\Scripts\python.exe tools\test_click_mail.py
echo.
pause
