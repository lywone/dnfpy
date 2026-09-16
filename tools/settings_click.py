# -*- coding: utf-8 -*-
"""
「修炼设置 → 应用」流程方法封装（settings_click.py）

流程：查找到「修炼设置」按钮 → 鼠标点击 → 延时 0.5s → 弹框出现后 → 查找并点击「应用」按钮

用法（管理员，游戏需处于修炼场界面，召唤怪物面板可见）：
    .venv\\Scripts\\python.exe settings_click.py

注意（重要实测结论）：
    DNF手游在腾讯应用宝模拟器中运行时会屏蔽所有 Windows 程序化鼠标输入
    （SendInput / mouse_event / PostMessage / SendMessage / WM_POINTER 均无效），
    因此本方法的“点击”在游戏里默认不生效，只会把定位结果和尝试过程记录下来。
    若要真正生效，可选：
      1) 在模拟器设置中开启 ADB 调试后改用 adb 注入（见文档 README_点击方案.md）
      2) 使用模拟器自带的“按键映射”把键盘键映射到按钮位置（半自动）
      3) 更换对自动化更友好的模拟器（夜神/雷电等，默认开放 adb）
"""
import sys
import os
import time
import ctypes
import ctypes.wintypes
import numpy as np
import cv2
from PIL import ImageGrab

# ---- 配置 ----
TITLE_KEY = "地下城与勇士"          # 窗口标题关键词
LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images", "settings_click.log")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_XIULIAN = [                    # 修炼设置按钮模板（按优先级尝试）
    os.path.join(BASE, "images", "template_xiulian.png"),     # 当前窗口同尺寸裁剪（首选）
    os.path.join(BASE, "images", "template_xiulian_v2.png"),  # 用户大窗口截图裁剪
]
TEMPLATE_APPLY = [                      # 应用按钮模板
    os.path.join(BASE, "images", "template_apply.png"),
]
SIFT_MIN_MATCHES = 8                    # SIFT 匹配点阈值
CLICK_WAIT = 0.5                        # 点修炼设置后等待弹框（秒）
CLICK_METHODS = ["post", "sendmsg", "real"]  # 点击尝试顺序

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


# ================= 基础工具 =================

def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S") + " " + msg
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


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
        user32.ShowWindow(hwnd, 9)
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


def capture_client(hwnd, path=None):
    left, top, right, bottom = get_client_rect(hwnd)
    pt = ctypes.wintypes.POINT(left, top)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    w, h = right - left, bottom - top
    img = ImageGrab.grab(bbox=(pt.x, pt.y, pt.x + w, pt.y + h))
    if path:
        img.save(path)
    return np.array(img)


# ================= 按钮定位（SIFT 模板匹配） =================

def find_button(templates, frame_rgb, name):
    """用 SIFT+FLANN 在画面中找按钮，返回客户区中心 (x, y)；找不到返回 None"""
    target = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    sift = cv2.SIFT_create()
    kp2, des2 = sift.detectAndCompute(target, None)
    if des2 is None or len(kp2) < 4:
        log(f"找不到「{name}」：画面特征点不足")
        return None
    for tpl_path in templates:
        template = cv2.imread(tpl_path)
        if template is None:
            continue
        kp1, des1 = sift.detectAndCompute(template, None)
        if des1 is None or len(kp1) < 4:
            continue
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        matches = flann.knnMatch(des1, des2, k=2)
        good = [m for m, n in matches if m.distance < 0.7 * n.distance]
        if len(good) < SIFT_MIN_MATCHES:
            log(f"「{name}」模板 {os.path.basename(tpl_path)} 匹配点不足: {len(good)}")
            continue
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if M is None:
            continue
        h, w = template.shape[:2]
        corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
        dst = cv2.perspectiveTransform(corners, M)
        cx = int(dst[:, 0, 0].mean())
        cy = int(dst[:, 0, 1].mean())
        log(f"找到「{name}」：客户区中心 ({cx},{cy})（模板 {os.path.basename(tpl_path)}，匹配点 {len(good)}）")
        return cx, cy
    log(f"「{name}」所有模板均未匹配成功")
    return None


# ================= 点击（多方案尝试） =================

def _click_post(hwnd, x, y):
    lparam = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
    r1 = user32.PostMessageW(hwnd, 0x0201, 0x0001, lparam)  # WM_LBUTTONDOWN
    time.sleep(0.05)
    r2 = user32.PostMessageW(hwnd, 0x0202, 0x0000, lparam)  # WM_LBUTTONUP
    return bool(r1 and r2)


def _click_sendmsg(hwnd, x, y):
    lparam = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
    user32.SendMessageW(hwnd, 0x0200, 0x0000, lparam)
    time.sleep(0.03)
    user32.SendMessageW(hwnd, 0x0201, 0x0001, lparam)
    time.sleep(0.03)
    user32.SendMessageW(hwnd, 0x0202, 0x0000, lparam)
    return True


def _click_real(hwnd, x, y):
    pt = ctypes.wintypes.POINT(x, y)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    user32.SetCursorPos(pt.x, pt.y)
    time.sleep(0.05)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    return True


def click_at(hwnd, x, y):
    """依次尝试多种鼠标点击方案，返回成功与否（仅表示消息已投递，不代表游戏响应）"""
    clickers = {
        "post": _click_post,
        "sendmsg": _click_sendmsg,
        "real": _click_real,
    }
    for method in CLICK_METHODS:
        try:
            ok = clickers[method](hwnd, x, y)
            log(f"点击 ({x},{y}) 方案[{method}] 已执行" + ("" if ok else "（投递失败）"))
            return True
        except Exception as e:
            log(f"点击 ({x},{y}) 方案[{method}] 异常: {e}")
    return False


def dialog_is_open(hwnd, frame):
    """检测修炼设置弹框是否已打开：找「应用」按钮"""
    return find_button(TEMPLATE_APPLY, frame, "应用") is not None


# ================= 主方法：修炼设置 → 应用 =================

def click_training_settings_and_apply():
    """
    核心方法（用户需求）：
      1. 查找并点击「修炼设置」按钮
      2. 延时 0.5s
      3. 弹框出现后查找并点击「应用」按钮
    返回流程是否执行完成（点击是否被游戏响应，需人工观察游戏画面确认）。
    """
    log("=" * 50)
    log("开始：修炼设置 → 应用")

    hwnd = get_hwnd()
    if not hwnd:
        log("未找到游戏窗口")
        return False
    log(f"游戏窗口 hwnd={hwnd}")

    force_foreground(hwnd)
    time.sleep(0.8)

    left, top, right, bottom = get_client_rect(hwnd)
    log(f"客户区 {right-left}x{bottom-top}")

    frame = capture_client(hwnd, os.path.join(BASE, "images", "flow_1.png"))

    # 如果弹框已开着，直接点应用
    if dialog_is_open(hwnd, frame):
        log("检测到修炼设置弹框已打开，跳过修炼设置按钮，直接点「应用」")
        pos = find_button(TEMPLATE_APPLY, frame, "应用")
        if pos:
            click_at(hwnd, pos[0], pos[1])
        time.sleep(1.0)
        capture_client(hwnd, os.path.join(BASE, "images", "flow_3_final.png"))
        log("完成")
        return True

    # 1. 找并点击修炼设置
    pos = find_button(TEMPLATE_XIULIAN, frame, "修炼设置")
    if not pos:
        log("失败：未找到「修炼设置」按钮（请确认游戏处于修炼场界面且召唤怪物面板可见）")
        return False
    click_at(hwnd, pos[0], pos[1])

    # 2. 延时 0.5s
    log(f"等待 {CLICK_WAIT}s 弹框出现…")
    time.sleep(CLICK_WAIT)

    # 3. 找并点击应用
    frame = capture_client(hwnd, os.path.join(BASE, "images", "flow_2_dialog.png"))
    pos = find_button(TEMPLATE_APPLY, frame, "应用")
    if not pos:
        log("失败：弹框未出现或「应用」按钮不在窗口可见范围内")
        log("（提示：窗口高度被游戏锁定在 ~832px，弹框底部被裁剪；请把游戏切到全屏/大窗口，")
        log("  或确认弹框内应用按钮在当前窗口下是否可见）")
        return False
    click_at(hwnd, pos[0], pos[1])

    time.sleep(1.0)
    capture_client(hwnd, os.path.join(BASE, "images", "flow_3_final.png"))
    log("流程执行完毕（点击是否生效请观察游戏画面）")
    return True


if __name__ == "__main__":
    ensure_admin()
    click_training_settings_and_apply()
