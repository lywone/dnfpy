# -*- coding: utf-8 -*-
"""验证 adb input tap 在游戏 display 上是否有效（点主城空地，看角色是否移动）"""
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auto_run as a

import numpy as np
import cv2


def shot():
    return a.capture_hdmi()


def diff_ratio(f0, f1):
    if f0 is None or f1 is None or f0.shape != f1.shape:
        return -1
    return float(np.mean(np.abs(f0.astype(int) - f1.astype(int))))


f0 = shot()
print(f"截图1: {None if f0 is None else (f0.shape[1], f0.shape[0])}")
if f0 is None:
    raise SystemExit("截图失败")

# 点主城地面空地（无害，角色走过去）
x, y = 1200, 650
print(f"[1] 默认 input tap ({x},{y}) …")
base = a.adb_base()
subprocess.run(base + ["shell", "input", "tap", str(x), str(y)],
               capture_output=True, timeout=30)
time.sleep(1.5)
f1 = shot()
d = diff_ratio(f0, f1)
print(f"    画面差: {d:.2f}  {'✓ tap 有效' if d > 3 else '✗ 无变化'}")

if d <= 3:
    # 尝试带 display 参数
    print(f"[2] input -d {a.DISPLAY_ID} tap ({x},{y}) …")
    subprocess.run(base + ["shell", "input", "-d", a.DISPLAY_ID, "tap", str(x), str(y)],
                   capture_output=True, timeout=30)
    time.sleep(1.5)
    f2 = shot()
    d2 = diff_ratio(f1, f2)
    print(f"    画面差: {d2:.2f}  {'✓ -d tap 有效' if d2 > 3 else '✗ 无变化'}")
