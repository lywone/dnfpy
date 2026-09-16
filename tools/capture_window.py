# -*- coding: utf-8 -*-
"""截取游戏窗口画面，用于定位按钮"""
import time
import pygetwindow as gw
from PIL import ImageGrab

TITLE_KEY = "地下城与勇士"
wins = [w for w in gw.getAllWindows()
        if TITLE_KEY in w.title and w.title.strip()]
if not wins:
    print("未找到游戏窗口")
    raise SystemExit(1)

win = wins[0]
try:
    win.restore()
    win.activate()
except Exception as e:
    print("激活失败:", e)
time.sleep(1)

left, top, right, bottom = win.left, win.top, win.right, win.bottom
print(f"窗口位置: left={left} top={top} right={right} bottom={bottom}")
print(f"窗口大小: {right-left} x {bottom-top}")
img = ImageGrab.grab(bbox=(left, top, right, bottom))
img.save(r"D:\code\dnfm-auto\images\capture_window.png")
print("已保存 D:\\code\\dnfm-auto\\images\\capture_window.png")
