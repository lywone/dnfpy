# -*- coding: utf-8 -*-
"""把游戏窗口拉大 → 强制置前 → 截图，确认「修炼设置」按钮是否可见"""
import time
import ctypes
import ctypes.wintypes
from PIL import ImageGrab

TITLE_KEY = "地下城与勇士"
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


hwnd = get_hwnd()
if not hwnd:
    print("未找到游戏窗口")
    raise SystemExit(1)
print(f"hwnd={hwnd}")

force_foreground(hwnd)
time.sleep(0.5)

# 拉大窗口到 1700x1000（窗口外框），保持左上角位置
rect = ctypes.wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
x, y = rect.left, rect.top
user32.MoveWindow(hwnd, x, y, 1700, 1000, True)
time.sleep(1.0)

left, top, right, bottom = get_client_rect(hwnd)
print(f"调整后客户区: {right-left}x{bottom-top}")
pt = ctypes.wintypes.POINT(left, top)
user32.ClientToScreen(hwnd, ctypes.byref(pt))
img = ImageGrab.grab(bbox=(pt.x, pt.y, pt.x + right - left, pt.y + bottom - top))
img.save(r"D:\code\dnfm-auto\images\window_enlarged.png")
print(f"已保存 window_enlarged.png（屏幕位置 {pt.x},{pt.y}）")
