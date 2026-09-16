# -*- coding: utf-8 -*-
"""诊断：SendInput 鼠标点击（记录返回值+错误码）→ 截图对比"""
import time
import ctypes
import ctypes.wintypes
import numpy as np
import cv2
from PIL import ImageGrab

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


def find_key_point(template_path, target_bgr, threshold=10):
    template = cv2.imread(template_path)
    if template is None:
        log(f"无法读取模板 {template_path}")
        return None
    sift = cv2.SIFT_create()
    kp1, des1 = sift.detectAndCompute(template, None)
    kp2, des2 = sift.detectAndCompute(target_bgr, None)
    if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
        log("特征点不足")
        return None
    FLANN_INDEX_KDTREE = 1
    index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)
    matches = flann.knnMatch(des1, des2, k=2)
    good = [m for m, n in matches if m.distance < 0.7 * n.distance]
    if len(good) < threshold:
        log(f"匹配点不足: {len(good)}")
        return None
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if M is None:
        log("单应矩阵失败")
        return None
    h, w = template.shape[:2]
    corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
    dst = cv2.perspectiveTransform(corners, M)
    cx = int(dst[:, 0, 0].mean())
    cy = int(dst[:, 0, 1].mean())
    log(f"找到按钮，中心 ({cx},{cy})，匹配点 {len(good)}")
    return cx, cy


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _fields_ = [("type", ctypes.c_ulong), ("u", _U)]


def sendinput_click_at(sx, sy):
    """SetCursorPos + SendInput 鼠标左键点击当前位置，返回 (down_ret, down_err, up_ret, up_err)"""
    user32.SetCursorPos(sx, sy)
    time.sleep(0.1)
    pt = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    log(f"鼠标实际位置 ({pt.x},{pt.y})，目标 ({sx},{sy})")
    down = INPUT()
    down.type = 0
    down.mi.dwFlags = 0x0002  # MOUSEEVENTF_LEFTDOWN
    r1 = user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
    e1 = kernel32.GetLastError()
    time.sleep(0.1)
    up = INPUT()
    up.type = 0
    up.mi.dwFlags = 0x0004  # MOUSEEVENTF_LEFTUP
    r2 = user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))
    e2 = kernel32.GetLastError()
    log(f"SendInput down: ret={r1} err={e1} | up: ret={r2} err={e2}")
    return r1, e1, r2, e2


hwnd = get_hwnd()
if not hwnd:
    log("未找到游戏窗口")
    raise SystemExit(1)
log(f"hwnd={hwnd}")

force_foreground(hwnd)
time.sleep(0.8)

frame1 = capture_client(hwnd, r"D:\code\dnfm-auto\images\step1.png")
target = cv2.cvtColor(frame1, cv2.COLOR_RGB2BGR)
pos = find_key_point(r"D:\code\dnfm-auto\images\template_xiulian.png", target)
if not pos:
    log("未找到「修炼设置」按钮")
    raise SystemExit(1)

pt = ctypes.wintypes.POINT(pos[0], pos[1])
user32.ClientToScreen(hwnd, ctypes.byref(pt))
log(f"按钮屏幕坐标 ({pt.x},{pt.y})")

sendinput_click_at(pt.x, pt.y)
time.sleep(1.0)

frame2 = capture_client(hwnd, r"D:\code\dnfm-auto\images\step2_dialog.png")
diff = np.mean(np.abs(frame1.astype(int) - frame2.astype(int)))
log(f"点击前后画面平均像素差: {diff:.2f}（0=完全相同）")
log("完成")
