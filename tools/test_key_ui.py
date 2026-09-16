# -*- coding: utf-8 -*-
"""PostMessage 键盘 UI 操作测试：ESC/Tab/方向键/Enter 看游戏是否有 UI 响应"""
import sys
import os
import time
import ctypes
import ctypes.wintypes
import numpy as np
from PIL import ImageGrab

TITLE_KEY = "地下城与勇士"
SW_RESTORE = 9
LOG_PATH = r"D:\code\dnfm-auto\images\test_log.txt"
BASE = r"D:\code\dnfm-auto"

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def ensure_admin():
    try:
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return
    if is_admin:
        return
    try:
        script = os.path.abspath(sys.argv[0])
        args = " ".join(f'"{a}"' for a in sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            f'"{script}" {args}'.strip(),
            os.path.dirname(script), 1)
    except Exception as e:
        print(f"请求管理员权限失败：{e}")
    sys.exit(0)


def log(msg):
    line = time.strftime("%H:%M:%S") + " " + msg
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_hwnd():
    found = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(hwnd, _):
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if TITLE_KEY in buf.value:
            found.append(hwnd)
        return True
    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def force_foreground(hwnd):
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    cur = kernel32.GetCurrentThreadId()
    fg = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(fg, None)
    attached = False
    if fg and fg_thread != cur:
        try:
            if user32.AttachThreadInput(cur, fg_thread, True):
                attached = True
        except Exception:
            pass
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(cur, fg_thread, False)


def get_client_rect(hwnd):
    rect = ctypes.wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def capture_client(hwnd, path):
    left, top, right, bottom = get_client_rect(hwnd)
    pt = ctypes.wintypes.POINT(left, top)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    w, h = right - left, bottom - top
    img = ImageGrab.grab(bbox=(pt.x, pt.y, pt.x + w, pt.y + h))
    img.save(path)
    return np.array(img)


def post_key(hwnd, vk, hold=0.1):
    user32.PostMessageW(hwnd, 0x0100, vk, 0)
    time.sleep(hold)
    user32.PostMessageW(hwnd, 0x0101, vk, 0)
    time.sleep(0.3)


VK_ESC = 0x1B
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_UP = 0x26
VK_DOWN = 0x28
VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_SPACE = 0x20

ensure_admin()
log(f"IsUserAnAdmin={ctypes.windll.shell32.IsUserAnAdmin()}")

hwnd = get_hwnd()
if not hwnd:
    log("未找到游戏窗口")
    raise SystemExit(1)
log(f"hwnd={hwnd}")

force_foreground(hwnd)
time.sleep(0.8)

frame0 = capture_client(hwnd, BASE + r"\images\u0.png")

# 依次测试各键，每键后截图对比
tests = [
    ("ESC", VK_ESC),
    ("Tab", VK_TAB),
    ("方向键下", VK_DOWN),
    ("Enter", VK_RETURN),
    ("ESC2", VK_ESC),
]
prev = frame0
for name, vk in tests:
    post_key(hwnd, vk)
    time.sleep(0.5)
    frame = capture_client(hwnd, BASE + f"\\images\\u_{name}.png")
    diff = np.mean(np.abs(prev.astype(int) - frame.astype(int)))
    log(f"{name}: 像素差 {diff:.2f}")
    prev = frame

log("完成")
