# -*- coding: utf-8 -*-
"""测试：SIFT 查找「修炼设置」→ 真实鼠标点击（SetCursorPos+mouse_event）→ 0.5s → 截图"""
import time
import ctypes
import ctypes.wintypes
import numpy as np
import cv2
from PIL import ImageGrab

TITLE_KEY = "地下城与勇士"
SW_RESTORE = 9
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
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


def _fg_title():
    fg = user32.GetForegroundWindow()
    if not fg:
        return ""
    length = user32.GetWindowTextLengthW(fg)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(fg, buf, length + 1)
    return buf.value


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


def real_click(hwnd, cx, cy):
    """真实鼠标点击窗口客户区坐标"""
    pt = ctypes.wintypes.POINT(cx, cy)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    user32.SetCursorPos(pt.x, pt.y)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    log(f"真实点击屏幕 ({pt.x},{pt.y})")


hwnd = get_hwnd()
if not hwnd:
    log("未找到游戏窗口")
    raise SystemExit(1)
log(f"hwnd={hwnd}")

force_foreground(hwnd)
time.sleep(0.8)
log(f"点击前前台窗口: {_fg_title()}")

frame = capture_client(hwnd, r"D:\code\dnfm-auto\images\step1.png")
target = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
pos = find_key_point(r"D:\code\dnfm-auto\images\template_xiulian.png", target)
if not pos:
    log("未找到「修炼设置」按钮")
    raise SystemExit(1)

real_click(hwnd, pos[0], pos[1])
time.sleep(0.5)
log(f"点击后前台窗口: {_fg_title()}")
capture_client(hwnd, r"D:\code\dnfm-auto\images\step2_dialog.png")
log("完成")
