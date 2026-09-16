# -*- coding: utf-8 -*-
"""测试（需管理员）：恢复窗口+强制置前 → 点击「修炼设置」→ 0.5s → 客户区截图"""
import time
import ctypes
import ctypes.wintypes
from PIL import ImageGrab

TITLE_KEY = "地下城与勇士"
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001
SW_RESTORE = 9

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


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


def click_client(hwnd, x_pct, y_pct):
    left, top, right, bottom = get_client_rect(hwnd)
    cw, ch = right - left, bottom - top
    cx = int(cw * x_pct)
    cy = int(ch * y_pct)
    lparam = (cy << 16) | (cx & 0xFFFF)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
    print(f"点击客户区 ({cx},{cy}) = ({x_pct:.3f},{y_pct:.3f})")


def capture_client(hwnd, path):
    left, top, right, bottom = get_client_rect(hwnd)
    pt = ctypes.wintypes.POINT(left, top)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    w, h = right - left, bottom - top
    img = ImageGrab.grab(bbox=(pt.x, pt.y, pt.x + w, pt.y + h))
    img.save(path)
    print(f"截图 {w}x{h} 位置 ({pt.x},{pt.y}) → {path}")
    print("前台窗口:", end=" ")
    fg = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(fg)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(fg, buf, length + 1)
    print(buf.value)


hwnd = get_hwnd()
if not hwnd:
    print("未找到游戏窗口")
    raise SystemExit(1)
print(f"hwnd={hwnd}")

force_foreground(hwnd)
time.sleep(0.8)
capture_client(hwnd, r"D:\code\dnfm-auto\images\pw_before.png")

click_client(hwnd, 0.144, 0.581)
time.sleep(0.5)

force_foreground(hwnd)
time.sleep(0.5)
capture_client(hwnd, r"D:\code\dnfm-auto\images\pw_after.png")
print("完成")
