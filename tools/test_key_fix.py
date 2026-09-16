# -*- coding: utf-8 -*-
"""修正 SendInput 结构体后重测键盘"""
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


# 标准 KEYBDINPUT（dwExtraInfo = ULONG_PTR = c_size_t）
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD),
        ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.wintypes.DWORD), ("u", _INPUTUNION)]


def send_key(vk, scan, up=False):
    inp = INPUT()
    inp.type = 1  # INPUT_KEYBOARD
    inp.ki.wVk = vk
    inp.ki.wScan = scan
    inp.ki.dwFlags = (0x0002 if up else 0) | 0x0008  # KEYEVENTF_KEYUP | SCANCODE
    inp.ki.time = 0
    inp.ki.dwExtraInfo = 0
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


SCAN_Q = 0x10
VK_Q = 0x51


ensure_admin()
log(f"IsUserAnAdmin={ctypes.windll.shell32.IsUserAnAdmin()}")
log(f"sizeof(INPUT)={ctypes.sizeof(INPUT)}")

hwnd = get_hwnd()
if not hwnd:
    log("未找到游戏窗口")
    raise SystemExit(1)
log(f"hwnd={hwnd}")

force_foreground(hwnd)
time.sleep(0.8)

left, top, right, bottom = get_client_rect(hwnd)
log(f"客户区 {right-left}x{bottom-top}")

frame0 = capture_client(hwnd, BASE + r"\images\kf_before.png")

# SendInput 按 Q（修正结构体）
log("--- SendInput 按 Q（修正结构体） ---")
for i in range(3):
    r1 = send_key(VK_Q, SCAN_Q, False)
    time.sleep(0.1)
    r2 = send_key(VK_Q, SCAN_Q, True)
    log(f"第{i+1}次: down={r1} up={r2}")
    time.sleep(0.5)
time.sleep(1.0)
frame1 = capture_client(hwnd, BASE + r"\images\kf_sendinput.png")
diff1 = np.mean(np.abs(frame0.astype(int) - frame1.astype(int)))
log(f"SendInput 按Q像素差: {diff1:.2f}")

# PostMessage 按 Q（对照）
log("--- PostMessage 按 Q ---")
for i in range(3):
    user32.PostMessageW(hwnd, 0x0100, VK_Q, 0)
    time.sleep(0.1)
    user32.PostMessageW(hwnd, 0x0101, VK_Q, 0)
    time.sleep(0.5)
time.sleep(1.0)
frame2 = capture_client(hwnd, BASE + r"\images\kf_postmsg.png")
diff2 = np.mean(np.abs(frame1.astype(int) - frame2.astype(int)))
log(f"PostMessage 按Q像素差: {diff2:.2f}")
log("完成")
