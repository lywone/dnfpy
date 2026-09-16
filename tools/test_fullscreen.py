# -*- coding: utf-8 -*-
"""发送 Alt+Enter 尝试切换游戏全屏"""
import time
import ctypes
import ctypes.wintypes

TITLE_KEY = "地下城与勇士"
SW_RESTORE = 9
LOG_PATH = r"D:\code\dnfm-auto\images\test_log.txt"

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


hwnd = get_hwnd()
if not hwnd:
    log("未找到游戏窗口")
    raise SystemExit(1)
log(f"hwnd={hwnd}")

force_foreground(hwnd)
time.sleep(0.6)

rect = ctypes.wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
log(f"切换前外框: {rect.right-rect.left}x{rect.bottom-rect.top}")

# 方法1: PostMessage Alt+Enter
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
VK_MENU = 0x12
VK_RETURN = 0x0D

# Alt down -> Enter down/up -> Alt up (PostMessage 到窗口)
user32.PostMessageW(hwnd, WM_SYSKEYDOWN, VK_MENU, 0)
time.sleep(0.05)
user32.PostMessageW(hwnd, WM_KEYDOWN, VK_RETURN, 0)
time.sleep(0.05)
user32.PostMessageW(hwnd, WM_KEYUP, VK_RETURN, 0)
time.sleep(0.05)
user32.PostMessageW(hwnd, WM_SYSKEYUP, VK_MENU, 0)
log("已发送 Alt+Enter (PostMessage)")
time.sleep(1.5)

rect = ctypes.wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
crect = ctypes.wintypes.RECT()
user32.GetClientRect(hwnd, ctypes.byref(crect))
log(f"切换后外框: {rect.right-rect.left}x{rect.bottom-rect.top} 客户区: {crect.right-crect.left}x{crect.bottom-crect.top}")

# 方法2: SendInput 键盘（若方法1无效）
if crect.right - crect.left <= 1500 or crect.bottom - crect.top <= 900:
    log("PostMessage 无效，尝试 SendInput 键盘 Alt+Enter")
    from ctypes import wintypes
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]
    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD),
                    ("ki", KEYBDINPUT)]
    def send_key(vk, up=False):
        inp = INPUT()
        inp.type = 1  # INPUT_KEYBOARD
        inp.ki.wVk = vk
        inp.ki.dwFlags = 0x0002 if up else 0
        return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    send_key(VK_MENU)      # Alt down
    send_key(VK_RETURN)    # Enter down
    send_key(VK_RETURN, True)  # Enter up
    send_key(VK_MENU, True)    # Alt up
    log("已发送 SendInput Alt+Enter")
    time.sleep(1.5)
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    user32.GetClientRect(hwnd, ctypes.byref(crect))
    log(f"SendInput 后外框: {rect.right-rect.left}x{rect.bottom-rect.top} 客户区: {crect.right-crect.left}x{crect.bottom-crect.top}")

log("完成")
