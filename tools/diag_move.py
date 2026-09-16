# -*- coding: utf-8 -*-
"""诊断：游戏窗口状态 + PostMessage 方向键是否有效"""
import ctypes
import sys
import os
import time

import numpy as np
from PIL import ImageGrab

user32 = ctypes.windll.user32


def ensure_admin():
    try:
        if bool(ctypes.windll.shell32.IsUserAnAdmin()):
            return
        script = os.path.abspath(sys.argv[0])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable,
                                            f'"{script}"', os.path.dirname(script), 1)
        sys.exit(0)
    except Exception as e:
        print(f"提权失败: {e}")


ensure_admin()

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "diag_move_out.txt")


def log(*args):
    msg = " ".join(str(a) for a in args)
    log(msg)
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


TITLE_KEY = "地下城"

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
VK_RIGHT = 0x27


def find_hwnd():
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if TITLE_KEY in buf.value and user32.IsWindowVisible(hwnd):
            found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(cb, 0)
    return found


def post_key(hwnd, down):
    sc = user32.MapVirtualKeyW(VK_RIGHT, 0)
    lparam = 1 | (sc << 16)
    if not down:
        lparam |= (1 << 30) | (1 << 31)
    return user32.PostMessageW(hwnd, WM_KEYDOWN if down else WM_KEYUP, VK_RIGHT, lparam)


def shot(hwnd):
    import ctypes.wintypes
    rect = ctypes.wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    pt = ctypes.wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return np.array(ImageGrab.grab(bbox=(pt.x, pt.y, pt.x + rect.right, pt.y + rect.bottom)))


wins = find_hwnd()
log(f"匹配窗口数: {len(wins)}")
for h, t in wins:
    log(f"  hwnd={h} 标题={t!r} 可见={bool(user32.IsWindowVisible(h))}")

is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
log(f"当前进程管理员: {is_admin}")

if not wins:
    log("未找到游戏窗口")
    raise SystemExit

hwnd, title = wins[0]
log(f"使用窗口: {hwnd} {title!r}")
log("前台窗口标题:", end=" ")
fg = user32.GetForegroundWindow()
n = user32.GetWindowTextLengthW(fg)
buf = ctypes.create_unicode_buffer(n + 1)
user32.GetWindowTextW(fg, buf, n + 1)
log(buf.value)

# 截图1
try:
    f0 = shot(hwnd)
    log(f"客户区截图: {f0.shape[1]}x{f0.shape[0]}")
except Exception as e:
    log(f"截图失败: {e}")
    f0 = None

# 发 → 按住 2 秒
log("PostMessage 按住 → 2 秒…")
post_key(hwnd, True)
time.sleep(2.0)
post_key(hwnd, False)
time.sleep(0.5)

# 截图2
try:
    f1 = shot(hwnd)
    diff = np.mean(np.abs(f0.astype(int) - f1.astype(int))) if f0 is not None else -1
    log(f"按 → 前后像素差: {diff:.2f}（>5 说明画面有变化）")
except Exception as e:
    log(f"截图失败: {e}")
