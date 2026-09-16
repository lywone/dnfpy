# -*- coding: utf-8 -*-
"""adb 点击修炼设置按钮测试：SIFT 定位 → 窗口坐标 → 游戏坐标 → HDMI 坐标 → tap"""
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

user32 = ctypes.windll.user32

# 游戏渲染分辨率与坐标换算参数
GAME_W, GAME_H = 1426, 804      # SurfaceView buffer 尺寸
HDMI_W, HDMI_H = 1207, 2141     # HDMI 屏
SCALE = HDMI_W / GAME_H         # 804 -> 1207 (1.501)


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
        log(f"SIFT 匹配点不足: {len(good)}")
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


def window_to_hdmi(wx, wy, w_w, w_h):
    """窗口坐标 -> 游戏坐标 -> HDMI 坐标（ROT_90 顺时针 + 缩放）"""
    gx = wx * GAME_W / w_w
    gy = wy * GAME_H / w_h
    hx = gy * SCALE
    hy = (GAME_W - gx) * SCALE
    return int(hx), int(hy)


def adb_tap(x, y, display=2):
    r = subprocess.run([ADB, "-s", "127.0.0.1:5555", "shell", "input", "-d", str(display), "tap", str(x), str(y)],
                       capture_output=True, text=True)
    log(f"adb tap HDMI({x},{y}) 输出: {r.stdout.strip()}{r.stderr.strip()}")
    return r


hwnd = get_hwnd()
if not hwnd:
    log("未找到游戏窗口")
    raise SystemExit(1)

frame, (w, h) = capture_client(hwnd, BASE + r"\images\adb1_before.png")
log(f"窗口 {w}x{h}")

pos = find_button(BASE + r"\images\template_xiulian.png", frame)
if not pos:
    log("未找到修炼设置按钮")
    raise SystemExit(1)
log(f"修炼设置按钮窗口坐标 {pos}")

hx, hy = window_to_hdmi(pos[0], pos[1], w, h)
log(f"HDMI 坐标 ({hx},{hy})")
adb_tap(hx, hy)
time.sleep(0.8)

frame2, _ = capture_client(hwnd, BASE + r"\images\adb2_after.png")
diff = np.mean(np.abs(frame.astype(int) - frame2.astype(int)))
log(f"点击前后像素差: {diff:.2f}")

# 检测弹框是否打开（找应用按钮模板）
apply_pos = find_button(BASE + r"\images\template_apply.png", frame2, min_matches=4)
if apply_pos:
    log(f"检测到弹框已打开！应用按钮位置 {apply_pos}")
else:
    log("未检测到弹框（应用按钮不可见）")
log("完成")
