# -*- coding: utf-8 -*-
"""adb 全流程：修炼设置 → 弹框 → 应用（SIFT 定位 + HDMI 坐标 tap）"""
import time
import ctypes
import ctypes.wintypes
import subprocess
import numpy as np
import cv2
from PIL import ImageGrab

TITLE_KEY = "地下城与勇士"
BASE = r"D:\code\dnfm-auto"
ADB = r"C:\Program Files\Tencent\Androws\Application\5.10.7400.6506\adb.exe"
LOG_PATH = BASE + r"\images\test_log.txt"

GAME_W, GAME_H = 1426, 804
SCALE = 1207 / GAME_H

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


def capture_client(hwnd, path=None):
    rect = ctypes.wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    pt = ctypes.wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    img = ImageGrab.grab(bbox=(pt.x, pt.y, pt.x + w, pt.y + h))
    if path:
        img.save(path)
    return np.array(img), (w, h)


def find_button(template_path, frame_rgb, min_matches=8):
    target = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    template = cv2.imread(template_path)
    if template is None:
        return None
    sift = cv2.SIFT_create()
    kp1, des1 = sift.detectAndCompute(template, None)
    kp2, des2 = sift.detectAndCompute(target, None)
    if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
        return None
    FLANN_INDEX_KDTREE = 1
    index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)
    matches = flann.knnMatch(des1, des2, k=2)
    good = [m for m, n in matches if m.distance < 0.7 * n.distance]
    if len(good) < min_matches:
        return None
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    if M is None:
        return None
    h, w = template.shape[:2]
    corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
    dst = cv2.perspectiveTransform(corners, M)
    return int(dst[:, 0, 0].mean()), int(dst[:, 0, 1].mean())


def w2h(wx, wy, w, h):
    gx = wx * GAME_W / w
    gy = wy * GAME_H / h
    return int(gy * SCALE), int((GAME_W - gx) * SCALE)


def adb_tap(hx, hy, display=2):
    subprocess.run([ADB, "-s", "127.0.0.1:5555", "shell", "input", "-d", str(display), "tap", str(hx), str(hy)],
                   capture_output=True, text=True)
    log(f"adb tap HDMI({hx},{hy})")


hwnd = get_hwnd()
if not hwnd:
    log("未找到游戏窗口")
    raise SystemExit(1)
log(f"hwnd={hwnd}")

force_foreground(hwnd)
time.sleep(0.8)

frame, (w, h) = capture_client(hwnd, BASE + r"\images\f0_before.png")
log(f"窗口 {w}x{h}")

# 1. 修炼设置按钮
pos = find_button(BASE + r"\images\template_xiulian.png", frame)
if not pos:
    log("未找到修炼设置按钮")
    raise SystemExit(1)
log(f"修炼设置按钮窗口坐标 {pos}")
hx, hy = w2h(pos[0], pos[1], w, h)
adb_tap(hx, hy)
time.sleep(0.8)

# 2. 弹框出现，找应用按钮
frame2, _ = capture_client(hwnd, BASE + r"\images\f1_dialog.png")
apply_pos = find_button(BASE + r"\images\template_apply.png", frame2, min_matches=4)
if not apply_pos:
    # 用更宽松的阈值再试
    apply_pos = find_button(BASE + r"\images\template_apply.png", frame2, min_matches=3)
if not apply_pos:
    log("未找到应用按钮（弹框未打开或按钮不可见）")
    raise SystemExit(1)
log(f"应用按钮窗口坐标 {apply_pos}")
hx2, hy2 = w2h(apply_pos[0], apply_pos[1], w, h)
adb_tap(hx2, hy2)
time.sleep(1.0)

# 3. 验证弹框关闭
frame3, _ = capture_client(hwnd, BASE + r"\images\f2_final.png")
diff = np.mean(np.abs(frame2.astype(int) - frame3.astype(int)))
log(f"点应用后像素差: {diff:.2f}")
log("完成")
