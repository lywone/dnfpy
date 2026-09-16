# -*- coding: utf-8 -*-
"""
极简版：获取「地下城与勇士：起源」窗口，直接按键盘 q w e r t
（底层按键：pydirectinput 扫描码，游戏无效时可切换 win32 SendInput 扫描码）

用法：
    python main.py          # 默认循环按键，Ctrl+C 停止
    python main.py once     # 只按一轮

可调参数：
    KEY_METHOD   按键方案："win32"（默认，PostMessage直发+SendInput兜底）/"directinput"
    LOOP          是否循环按键
    HOLD_TIME     每个键按下的保持时长（秒），游戏技能太短可能识别不到
    KEY_INTERVAL  键与键之间的间隔（秒）
    ROUND_INTERVAL 每轮之间的间隔（秒）
"""
import sys
import os
import time
import ctypes
import winsound
import pygetwindow as gw
import pymsgbox

# ---- 配置 ----
TITLE_KEY = "地下城与勇士"     # 窗口标题关键词（半角/全角冒号都能匹配）
KEYS = ["q"]  # 要按的键
KEY_METHOD = "win32"   # win32=PostMessage直发窗口+SendInput兜底 / directinput=pydirectinput(扫描码)
LOOP = True                  # True=持续循环；False=只按一轮
HOLD_TIME = 0.15             # 每个键按下的保持时长（秒）
KEY_INTERVAL = 0.2           # 键与键之间的间隔（秒）
ROUND_INTERVAL = 1.0         # 每轮之间的间隔（秒）

# ================= 按键发送底层 =================

try:
    import pydirectinput
    _HAS_DIRECTINPUT = True
except Exception:
    _HAS_DIRECTINPUT = False


def _sendinput_key(key: str, down: bool):
    """win32 SendInput 发送按键（使用扫描码，最贴近物理键盘）"""
    user32 = ctypes.windll.user32
    vk = ord(key.upper())
    scancode = user32.MapVirtualKeyW(vk, 0)

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT)]
        _fields_ = [("type", ctypes.c_ulong), ("u", _U)]

    KEYEVENTF_SCANCODE = 0x0008
    KEYEVENTF_KEYUP = 0x0002

    inp = INPUT()
    inp.type = 1  # INPUT_KEYBOARD
    inp.ki.wVk = 0
    inp.ki.wScan = scancode
    inp.ki.dwFlags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if not down else 0)
    inp.ki.time = 0
    inp.ki.dwExtraInfo = 0
    ret = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if ret != 1:
        raise RuntimeError(f"SendInput 失败（返回 {ret}）")


# ---------------- PostMessage 直发窗口（绕过全局输入系统） ----------------
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101


def _get_hwnd_by_title():
    """按标题关键词枚举所有窗口，返回第一个匹配的句柄"""
    user32 = ctypes.windll.user32
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


def _foreground_window_title():
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _force_foreground(hwnd):
    """强制把窗口置为前台（绕过 Windows 的前台锁定限制）"""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
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


def _post_key(hwnd, key: str, down: bool):
    """PostMessage 直接向窗口投递 WM_KEYDOWN/WM_KEYUP"""
    user32 = ctypes.windll.user32
    vk = ord(key.upper())
    sc = user32.MapVirtualKeyW(vk, 0)
    lparam = 1 | (sc << 16)          # repeat count + 扫描码
    if not down:
        lparam |= (1 << 30) | (1 << 31)  # 键释放标志
    return user32.PostMessageW(hwnd, WM_KEYDOWN if down else WM_KEYUP, vk, lparam)


def send_key(key: str):
    """按下并抬起一个键，返回所用方案名

    实测结论（腾讯应用宝模拟器 + DNF手游）：
    - PostMessage 直发 WM_KEYDOWN/UP 到游戏窗口 → 有效（游戏处理键盘消息）
    - SendInput / pydirectinput / pyautogui → 均被游戏屏蔽（SendInput 返回 0）
    因此默认且唯一推荐方案就是 PostMessage 直发。
    """
    if KEY_METHOD == "directinput" and _HAS_DIRECTINPUT:
        pydirectinput.keyDown(key)
        time.sleep(HOLD_TIME)
        pydirectinput.keyUp(key)
        return "directinput"

    # win32：PostMessage 直发游戏窗口（已验证有效）
    hwnd = _get_hwnd_by_title()
    if hwnd:
        _force_foreground(hwnd)
        r1 = _post_key(hwnd, key, True)
        time.sleep(HOLD_TIME)
        r2 = _post_key(hwnd, key, False)
        if r1 and r2:
            return f"win32-post(hwnd={hwnd})"
        print(f"  [警告] PostMessage 投递失败（r1={r1}, r2={r2}），尝试 SendInput 兜底…")
    try:
        _sendinput_key(key, True)
        time.sleep(HOLD_TIME)
        _sendinput_key(key, False)
        return "win32-sendinput"
    except Exception as e:
        # SendInput 被游戏/模拟器屏蔽时不崩溃，只提示
        print(f"  [警告] SendInput 兜底也失败：{e}")
        return "win32-failed"


# ================= 主流程 =================

def find_windows():
    """按标题关键词查找窗口，返回窗口列表"""
    wins = gw.getWindowsWithTitle(TITLE_KEY)
    if not wins:
        wins = [w for w in gw.getAllWindows()
                if TITLE_KEY in w.title and w.title.strip()]
    return wins


def beep(freq: int = 880, dur: int = 250):
    """播放提示音（静默失败，不影响主流程）"""
    try:
        winsound.Beep(freq, dur)
    except Exception:
        pass


def ensure_admin():
    """游戏通常以管理员运行，普通权限的按键会被系统(UIPI)拦截。
    非管理员时自动弹 UAC 以管理员身份重启本脚本。"""
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


def main():
    ensure_admin()

    method = KEY_METHOD
    if method == "directinput" and not _HAS_DIRECTINPUT:
        method = "win32"
        print("pydirectinput 不可用，已回退到 win32 SendInput 方案")

    wins = find_windows()
    if not wins:
        print(f"未找到标题包含「{TITLE_KEY}」的窗口")
        print("当前打开的窗口：")
        for w in gw.getAllWindows():
            if w.title.strip():
                print("  -", w.title)
        beep(200, 400)
        pymsgbox.alert(f"未找到「{TITLE_KEY}」窗口，请先打开游戏再运行。", "dnfm-auto 按键脚本")
        return

    win = wins[0]
    print(f"找到窗口：{win.title}")
    beep(880, 150)   # 找到窗口：提示音
    try:
        win.restore()
        win.activate()
    except Exception as e:
        print(f"激活窗口失败（{e}），仍会尝试按键")
    time.sleep(1)
    hwnd = _get_hwnd_by_title()
    print(f"游戏窗口句柄：{hwnd}")
    print(f"当前前台窗口：{_foreground_window_title()}")

    rounds = 0
    print(f"开始按键：{' → '.join(KEYS)}" +
          ("（循环中，Ctrl+C 停止）" if LOOP else "（共一轮）"))
    beep(1175, 200)  # 开始按键：提示音
    try:
        while True:
            for key in KEYS:
                scheme = send_key(key)
                if len(KEYS) == 1:
                    print(f"已按 {key}（方案：{scheme}）")
                time.sleep(KEY_INTERVAL)
            rounds += 1
            print(f"第 {rounds} 轮完成")
            if not LOOP or (len(sys.argv) > 1 and sys.argv[1] == "once"):
                break
            time.sleep(ROUND_INTERVAL)
        beep(880, 200)  # 正常结束：提示音
        pymsgbox.alert(f"已完成 {rounds} 轮按键（{' → '.join(KEYS)}）。", "dnfm-auto 按键脚本")
    except KeyboardInterrupt:
        beep(660, 200)
        print("\n已停止")


if __name__ == "__main__":
    main()
