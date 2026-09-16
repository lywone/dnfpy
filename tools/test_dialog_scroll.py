# -*- coding: utf-8 -*-
"""综合测试：点修炼设置→弹框→滚轮滚动→应用按钮是否可见"""
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


def real_click(hwnd, cx, cy):
    pt = ctypes.wintypes.POINT(cx, cy)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    user32.SetCursorPos(pt.x, pt.y)
    time.sleep(0.05)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    log(f"点击客户区 ({cx},{cy}) -> 屏幕({pt.x},{pt.y})")


def send_wheel(hwnd, cx, cy, delta):
    """向窗口发滚轮（PostMessage + SendInput 双保险）"""
    pt = ctypes.wintypes.POINT(cx, cy)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    # PostMessage WM_MOUSEWHEEL
    wparam = (delta << 16) | 0
    lparam = (pt.y << 16) | (pt.x & 0xFFFF)
    user32.PostMessageW(hwnd, 0x020A, wparam, lparam)
    # SendInput 滚轮（需鼠标在窗口上）
    user32.SetCursorPos(pt.x, pt.y)
    time.sleep(0.05)
    from ctypes import wintypes
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]
    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("mi", MOUSEINPUT)]
    inp = INPUT()
    inp.type = 0  # INPUT_MOUSE
    inp.mi.dwFlags = 0x0800  # MOUSEEVENTF_WHEEL
    inp.mi.mouseData = delta & 0xFFFFFFFF
    ret = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    log(f"滚轮 delta={delta} PostMessage+SendInput(ret={ret})")


hwnd = get_hwnd()
if not hwnd:
    log("未找到游戏窗口")
    raise SystemExit(1)
log(f"hwnd={hwnd}")

force_foreground(hwnd)
time.sleep(0.8)

left, top, right, bottom = get_client_rect(hwnd)
log(f"客户区 {right-left}x{bottom-top}")

# 1. 点击修炼设置按钮 (355, 799)（OCR 确认位置）
real_click(hwnd, 355, 799)
time.sleep(0.8)
frame1 = capture_client(hwnd, BASE + r"\images\w_dialog.png")
log("已点修炼设置，截图 w_dialog.png")

# 2. 滚轮向下滚动弹框（5 格）
for i in range(5):
    send_wheel(hwnd, 800, 400, -120)
    time.sleep(0.15)
time.sleep(0.8)
frame2 = capture_client(hwnd, BASE + r"\images\w_scrolled.png")
diff = np.mean(np.abs(frame1.astype(int) - frame2.astype(int)))
log(f"滚动前后像素差: {diff:.2f}")

# 3. 再滚动更多
for i in range(5):
    send_wheel(hwnd, 800, 400, -120)
    time.sleep(0.15)
time.sleep(0.8)
capture_client(hwnd, BASE + r"\images\w_scrolled2.png")
log("完成")
