# -*- coding: utf-8 -*-
"""严格验证 adb tap：点击主城「角色」按钮(742,947)，面板弹出=有效"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auto_run as a

import numpy as np


def shot():
    return a.capture_hdmi()


def diff(f0, f1):
    if f0 is None or f1 is None or f0.shape != f1.shape:
        return -1
    return float(np.mean(np.abs(f0.astype(int) - f1.astype(int))))


f0 = shot()
print(f"截图1: {None if f0 is None else (f0.shape[1], f0.shape[0])}")

x, y = 742, 947   # 主城「角色」按钮（弹面板，视觉反馈强）
base = a.adb_base()

print(f"[1] 默认 input tap ({x},{y}) …")
subprocess.run(base + ["shell", "input", "tap", str(x), str(y)],
               capture_output=True, timeout=30)
time.sleep(1.5)
f1 = shot()
d1 = diff(f0, f1)
print(f"    画面差: {d1:.2f}  {'✓ 有效' if d1 > 30 else '✗ 无反应'}")

if d1 <= 30:
    print(f"[2] input -d {a.DISPLAY_ID} tap ({x},{y}) …")
    subprocess.run(base + ["shell", "input", "-d", a.DISPLAY_ID, "tap", str(x), str(y)],
                   capture_output=True, timeout=30)
    time.sleep(1.5)
    f2 = shot()
    d2 = diff(f1, f2)
    print(f"    画面差: {d2:.2f}  {'✓ -d 有效' if d2 > 30 else '✗ 无反应'}")

# 关闭面板：ESC
print("[3] PostMessage ESC 关闭面板…")
hwnd = a.find_game_window()
if hwnd:
    a.send_key(hwnd, 0x1B, True)
    time.sleep(0.08)
    a.send_key(hwnd, 0x1B, False)
    time.sleep(1.0)
    f3 = shot()
    print(f"    画面差(关面板): {diff(f2 or f1, f3):.2f}")
