# -*- coding: utf-8 -*-
"""
《地下城与勇士：起源》自动过图挂机脚本 auto_run.py
====================================================
运行环境：Windows（游戏在应用宝模拟器中运行）
依赖：opencv-python、numpy、pillow（本工程已装于 .venv）

图片文件统一放在本脚本同级的 templates/ 文件夹：
  templates/template_challenge.png  「再次挑战」按钮模板（必须）
  templates/challenge_raw.png       --capture 截取的原始画面（自动生成）

流程（循环）：
  阶段1 跑图：
    按住 → 前进 2~3 秒；在 → 保持按下的同时，↑2秒 / ↓2秒 交替移动，累计约20秒
  阶段2 检测「再次挑战」：
    截取游戏画面（adb screencap -d 3）→ 模板匹配；未检测到 → 按住 → 前进2秒 → 再检测，直到检测到
  阶段3 触发：
    按 F10 → 等3秒 → 再检测；若仍有「再次挑战」→ 再按 F10 → 直到检测不到 → 回到阶段1

用法：
  python auto_run.py             正常挂机（Ctrl+C 停止）
  python auto_run.py --capture   截取当前 HDMI 游戏画面到 templates/，用于制作模板
  python auto_run.py --selftest  自测「再次挑战」检测逻辑（不连接游戏）
"""
import os          # 操作系统接口：拼接路径、判断文件是否存在
import sys         # 系统接口：sys.argv 读取命令行参数（--selftest/--testmove/--capture）
import glob        # 路径通配：glob.glob 在安装目录中查找 adb.exe
import time        # 时间控制：按键保持时长、界面等待、轮次延时
import subprocess  # 子进程：调用 adb.exe 执行截图/点击/滑动/按键
import tempfile    # 临时目录：截图暂存文件放到系统临时目录

import cv2         # OpenCV：截图读取、模板匹配（matchTemplate）、颜色判断
import numpy as np  # 数值计算：合成自测画面、图像数组运算
import json        # 配置读写：config.json 保存窗口尺寸等持久化设置

# ---------------- 配置 ----------------
TITLE_KEY = "地下城"                 # 游戏窗口标题关键词（用于 EnumWindows 找窗口）
# 模拟器重启后 adb 设备名/display 编号都会变，启动时自动探测：
ADB_DEVICE = None                    # 探测结果：如 "emulator-5554"（None=尚未探测）
DISPLAY_ID = None                    # 探测结果：如 "2"（None=尚未探测/用默认）
DISPLAY_CANDIDATES = ["2", "0", "3", "1", None]  # 优先尝试的 display 顺序（先试常用的 2）
TMP_REMOTE = "/sdcard/_dnfm_shot.png"  # 游戏画面先截图保存到安卓设备的这个路径
TMP_LOCAL = os.path.join(tempfile.gettempdir(), "_dnfm_shot.png")  # 再从设备 pull 到本机临时路径
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")  # 配置文件（记录窗口尺寸）
SIZE_TOLERANCE = 0.02               # 窗口尺寸容差（±2%：模拟器边框微小差异不影响模板匹配）

BACK_STEP = 0.2                     # 阶段1：先向后跑（←）的秒数
FWD_STEP = 2.0                      # 阶段1：向前直跑（→）的秒数
DIAG_UP_STEP = 0.5                  # 阶段1：斜上跑（→+↑）单次秒数
DIAG_DOWN_STEP = 1.0                # 阶段1：斜下跑（→+↓）单次秒数（用户要求 0.5s → 1s）
ROUND_SECONDS = 15.0                # 阶段1：一轮跑图总时长（之后检查按钮）
MOVE_STEP = 2.0                     # 阶段2：未检测到时继续前进的秒数
F10_WAIT = 3.0                      # 阶段3：按 F10 后等待复查秒数
MATCH_TH = 0.60                     # 「再次挑战」匹配相似度阈值（主城误匹配最高约 0.58）
CONFIRM_TH = 0.50                   # 「确认」按钮独立阈值（模板简单纯色底，真实按钮匹配偏低）
REWARD_TH = 0.70                    # 「领奖结算」专用阈值（城镇同位置金字按钮误匹配 0.606，结算真按钮 1.0）
RECHECK_ROUNDS = 10                 # 发现「领奖结算」后复查「再次挑战」的次数（10 次）
RECHECK_WAIT = 2.0                  # 复查「再次挑战」的间隔秒数（2s 一次）
STAGE2_TIMEOUT = 180.0              # 阶段2 检测「再次挑战/领奖结算」的超时秒数（3 分钟）；超时提示音并重新跑图
SCALES = (0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0)  # 多尺度匹配（覆盖分辨率差异，最大 2.0 倍）
SHOT_FAIL_LIMIT = 5                 # 连续截图失败次数上限（模拟器断开判定）

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 脚本所在目录（作为工程根）
IMG_DIR = os.path.join(BASE_DIR, "templates")        # 图片统一放这里（模板图目录）
TEMPLATE_PATH = os.path.join(IMG_DIR, "template_challenge.png")   # 「再次挑战」模板路径
TEMPLATE_REWARD = os.path.join(IMG_DIR, "template_reward.png")    # 「领奖结算」模板路径
TEMPLATE_SETTLE = os.path.join(IMG_DIR, "template_settle.png")    # 「结算」按钮模板路径
TEMPLATE_CONFIRM = os.path.join(IMG_DIR, "template_confirm.png")  # 「确认」按钮模板路径
TEMPLATE_CHALLENGE_CONFIRM = os.path.join(IMG_DIR, "template_challenge_confirm.png")  # 「再次挑战」后确认弹框的「确认」按钮模板（红底白字 75x35）
TEMPLATE_TOWN = os.path.join(IMG_DIR, "template_town.png")        # 「返回城镇」按钮模板路径
TEMPLATE_MAIL = os.path.join(IMG_DIR, "template_mail.png")        # 「邮箱」图标模板路径
TEMPLATE_CLAIM = os.path.join(IMG_DIR, "template_claim.png")      # 「领取全部物品」按钮模板路径
TEMPLATE_MAIL_CONFIRM = os.path.join(IMG_DIR, "template_mail_confirm.png")  # 领取后「确认」模板路径
TEMPLATE_MAIL_BACK = os.path.join(IMG_DIR, "template_mail_back.png")        # 邮箱界面「返回邮箱」模板路径
TEMPLATE_SHOP = os.path.join(IMG_DIR, "template_shop.png")        # 「神秘商店」图标（城镇顶部）模板路径
TEMPLATE_SHOP_BACK = os.path.join(IMG_DIR, "template_shop_back.png")  # 商店界面「返回」按钮模板路径
TEMPLATE_BUY = os.path.join(IMG_DIR, "template_buy.png")          # 「购买」按钮模板路径
TEMPLATE_BUY_POPUP = os.path.join(IMG_DIR, "template_buy_popup.png")  # 「购买物品」弹框模板路径
TEMPLATE_BUY_POPUP_BTN = os.path.join(IMG_DIR, "template_buy_popup_btn.png")  # 购买弹框内「购买」按钮模板（红底白字 74x40）
TEMPLATE_BUY_DONE = os.path.join(IMG_DIR, "template_buy_done.png")    # 「完成购买」奖励弹窗模板路径
TEMPLATE_BUY_DONE_CONFIRM = os.path.join(IMG_DIR, "template_buy_done_confirm.png")  # 奖励弹窗「确认」模板路径
TEMPLATE_REFRESH_FREE = os.path.join(IMG_DIR, "template_refresh_free.png")  # 「1000免费 立即刷新」（免费态）模板路径
TEMPLATE_REFRESH = os.path.join(IMG_DIR, "template_refresh.png")
TEMPLATE_POPUP = os.path.join(IMG_DIR, "template_popup_guide.png")  # 活动引导弹窗标题「3分钟直升15万」模板路径（按 ESC 关闭目标）  # 「1000 立即刷新」付费态（同源裁剪 0.83）模板路径

# 切换角色（选角）相关模板
TEMPLATE_CHAR_SELECT = os.path.join(IMG_DIR, "template_char_select.png")      # 「选角」按钮模板路径
TEMPLATE_CHALLENGE_PANEL = os.path.join(IMG_DIR, "template_challenge_panel.png")  # 「挑战进度」面板标题模板路径
TEMPLATE_REFRESHABLE = os.path.join(IMG_DIR, "template_refreshable.png")      # 「可刷新」按钮模板路径
TEMPLATE_START_YELLOW = os.path.join(IMG_DIR, "template_start_yellow.png")    # 「开始游戏」黄色（可点）模板路径
TEMPLATE_START_GRAY = os.path.join(IMG_DIR, "template_start_gray.png")        # 「开始游戏」灰色（不可点）模板路径
TEMPLATE_START_CONFIRM = os.path.join(IMG_DIR, "template_start_confirm.png")  # 点开始游戏后弹框「确认」（棕底白字 186x79）模板路径

# 分解装备相关模板
TEMPLATE_BAG = os.path.join(IMG_DIR, "template_bag.png")                # 「背包」图标（主页右下）模板路径
TEMPLATE_DECOMPOSE_BTN = os.path.join(IMG_DIR, "template_decompose_btn.png")  # 「分解」入口按钮（背包界面）模板路径
TEMPLATE_DECOMPOSE_TITLE = os.path.join(IMG_DIR, "template_decompose_title.png")  # 分解弹框标题栏（含 ×）模板路径
TEMPLATE_DECOMPOSE_GO = os.path.join(IMG_DIR, "template_decompose_go.png")      # 弹框内金黄「分解」按钮模板路径
TEMPLATE_DECOMPOSE_CONFIRM = os.path.join(IMG_DIR, "template_decompose_confirm.png")  # 「确认」按钮（棕黄底）模板路径
TEMPLATE_DECOMPOSE_HIGHVALUE = os.path.join(IMG_DIR, "template_decompose_highvalue.png")  # 高价值二次确认弹窗模板路径
TEMPLATE_DECOMPOSE_RESULT = os.path.join(IMG_DIR, "template_decompose_result.png")  # 「获得道具」弹窗模板路径
TEMPLATE_BAG_BACK = os.path.join(IMG_DIR, "template_bag_back.png")      # 背包界面返回（未用，BACK 更可靠）模板路径
RAW_PATH = os.path.join(IMG_DIR, "challenge_raw.png")  # --capture 截取的原始画面保存路径

MAIL_TH = 0.60                 # 「邮箱」图标匹配阈值（城镇实测 0.779）
CLAIM_TH = 0.65                # 「领取全部物品」阈值（实测 0.974，城镇底部误匹配 0.586）
MAIL_CONFIRM_TH = 0.60         # 领取后「确认」按钮阈值
MAIL_BACK_TH = 0.60            # 「返回邮箱」阈值（同源模板：界面 1.0 / 城镇 0.377）
MAIL_WAIT_AFTER_TOWN = 5.0     # 返回城镇后等待秒数（再开邮箱）
MAIL_ROUNDS = 10               # 邮箱领取最大尝试轮数

SHOP_TH = 0.60                 # 「神秘商店」图标阈值（同源模板：城镇 1.0）
SHOP_BACK_TH = 0.60            # 商店「返回」按钮阈值（同源模板：商店 1.0 / 城镇 0.354）
BUY_TH = 0.60                  # 「购买」按钮阈值（实测 0.72-0.93）
POPUP_TH = 0.60                # 「购买物品」弹框阈值（实测 0.66）
BUY_DONE_TH = 0.60             # 「完成购买」奖励弹窗阈值（同源 1.0）
BUY_DONE_CONFIRM_TH = 0.60     # 奖励弹窗「确认」按钮阈值（同源 1.0）
REFRESH_FREE_TH = 0.60         # 「免费刷新」按钮阈值（免费态显示，付费态界面 0.45）
REFRESH_TH = 0.60              # 「付费刷新」按钮阈值（同源模板实测 0.61-0.83）
SHOP_WAIT_AFTER_HOME = 2.0     # 回主页面后等待秒数（再开商店）
SHOP_ROUNDS = 10               # 商店刷新购买最大循环轮数

CHAR_SELECT_TH = 0.60          # 「选角」按钮阈值（同源模板 1.0）
PANEL_TH = 0.60                # 「挑战进度」面板标题阈值（实测 0.656）
REFRESHABLE_TH = 0.65          # 「可刷新」阈值（面板列表区内检测，排除右上角误匹配 0.684）
START_YELLOW_TH = 0.60         # 「开始游戏」黄色阈值（灰态 0.48 不触发，黄态才触发）
START_CONFIRM_TH = 0.60        # 点开始游戏后弹框「确认」阈值
CHAR_CONFIRM_WAIT = 10.0       # 点「开始游戏」后等待秒数（再检查确认按钮）
CHAR_EXIT_WAIT = 5.0           # 点「确认」后等待秒数（再退出脚本）
CHAR_WAIT_AFTER_HOME = 2.0     # 返回主页面后等待秒数（再点选角）
CHAR_SCROLL_TOP_SECONDS = 9.0  # 保留：旧「滚到顶」时长（新逻辑不再用）
CHAR_SCROLL_DOWN_SECONDS = 30.0  # 先慢慢往底部拖找「可刷新」的时长上限
CHAR_SCROLL_UP_SECONDS = 60.0    # 底部没找到后往上滚找「可刷新」的时长上限
CHAR_DRAG_MS = 3000            # 每次慢速长拖时长（毫秒，模拟按住鼠标拖动）
CHAR_REFRESH_RETRY = 8         # 保留：未变黄时继续往下滚找下一个可刷新的最大轮数
CHAR_SCROLL_MAX = 30           # 往下滚动查找「可刷新」行的最大步数

# ---------------- 分解装备 ----------------
DECOMPOSE_WAIT_AFTER_MAIL = 2.0   # 邮件完成后等待秒数（再点背包）
DECOMPOSE_TH = 0.60               # 分解相关模板匹配阈值
DECOMPOSE_MAX_TRY = 10            # 各阶段最大尝试轮数
# 实测固定坐标（画面 2143x1204）：
DECOMPOSE_OUTER_CONFIRM = (1241, 955)   # 外层提示弹窗「确认」（分解后至少获得道具）
DECOMPOSE_INNER_CONFIRM = (1235, 751)   # 内层高价值二次确认「确认」（确定要出售/分解吗）
DECOMPOSE_RESULT_CONFIRM = (1069, 756)  # 「获得道具」弹窗「确认」
DECOMPOSE_CLOSE_X = (2035, 134)         # 分解弹框右上角 ×（实测有效）

# ---------------- 提示 ----------------
def beep(ok=True):
    """提示音：成功 1175Hz / 失败 200Hz（Windows 专属，失败静默）"""
    try:                       # 尝试播放提示音（可能因环境无声音设备而失败）
        import winsound        # Windows 内置的声音播放模块
        winsound.Beep(1175 if ok else 200, 300 if ok else 600)  # 成功音高1175/时长300ms，失败音高200/时长600ms
    except Exception:          # 播放失败（如非 Windows 环境）
        pass                   # 静默忽略，不影响主流程


def msgbox(text, title="dnfm-auto 挂机"):
    """弹窗（Windows 专属，失败降级为打印）"""
    try:                       # 尝试弹窗（可能未安装 pymsgbox 库）
        import pymsgbox        # 弹窗库（第三方，随工程安装）
        pymsgbox.alert(text, title)  # 弹出阻塞式提示框，等待用户点确定
        return                 # 弹窗成功则直接返回
    except Exception:          # 弹窗失败（库缺失等）
        pass                   # 忽略异常，走打印降级
    print(f"\n>>> {title}: {text}")  # 用打印代替弹窗，保证信息不丢失


# ---------------- 键盘（Windows PostMessage，唯一有效通道） ----------------
WM_KEYDOWN = 0x0100        # Windows 消息：按键按下
WM_KEYUP = 0x0101           # Windows 消息：按键松开
WM_MOUSEWHEEL = 0x020A      # Windows 消息：鼠标滚轮
VK = {"right": 0x27, "up": 0x26, "down": 0x28, "left": 0x25, "f10": 0x79}  # 虚拟键码：→=0x27 ↑=0x26 ↓=0x28 ←=0x25 F10=0x79


def ensure_admin():
    """游戏通常以管理员运行，普通权限进程向它发消息会被系统 UIPI 拦截。
    非管理员时自动弹 UAC 以管理员身份重启本脚本。"""
    try:                         # 尝试检测当前进程权限
        import ctypes            # Windows API 调用库
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())  # 查询当前进程是否管理员权限
    except Exception:            # 检测失败（非 Windows）
        return                   # 无法检测则直接继续（后续按键会失败并报错）
    if is_admin:                 # 已经是管理员权限
        return                   # 无需提权，直接继续
    try:                         # 尝试请求提权重启
        script = os.path.abspath(sys.argv[0])  # 获取当前脚本的绝对路径
        args = " ".join(f'"{a}"' for a in sys.argv[1:])  # 把原命令行参数拼成带引号的字符串
        ctypes.windll.shell32.ShellExecuteW(  # 调用 ShellExecute 以管理员身份启动
            None, "runas", sys.executable,  # runas=提权运行；运行的是 python.exe
            f'"{script}" {args}'.strip(),   # 传给 python 的完整命令（脚本路径+参数）
            os.path.dirname(script), 1)      # 工作目录=脚本目录；SW_SHOWNORMAL=显示窗口
    except Exception as e:       # 提权请求失败
        print(f"请求管理员权限失败：{e}")  # 打印错误原因
    sys.exit(0)                  # 退出当前（非管理员）进程，让新管理员进程接管


def force_foreground(hwnd):
    """强制把游戏窗口置为前台（绕过 Windows 的前台锁定限制）"""
    user32, ctypes = _win_user32()  # 获取 user32 API 和 ctypes 模块
    kernel32 = ctypes.windll.kernel32  # 获取 kernel32 API（查线程 ID 用）
    cur = kernel32.GetCurrentThreadId()  # 当前进程的线程 ID
    fg = user32.GetForegroundWindow()    # 当前前台窗口句柄
    fg_thread = user32.GetWindowThreadProcessId(fg, None)  # 前台窗口所属线程 ID
    attached = False             # 标记是否已附加输入线程（用于绕过前台锁）
    if fg and fg_thread != cur:  # 存在前台窗口且不是本进程的线程
        try:                     # 尝试附加线程输入
            if user32.AttachThreadInput(cur, fg_thread, True):  # 把当前线程输入附加到前台线程
                attached = True  # 附加成功则记录标记
        except Exception:        # 附加失败（权限等）
            pass                 # 忽略，继续尝试其他置前方式
    try:                         # 开始置前操作
        user32.ShowWindow(hwnd, 5)  # SW_SHOW：显示窗口（最小化时恢复）
        user32.BringWindowToTop(hwnd)  # 把窗口带到最上层
        user32.SetForegroundWindow(hwnd)  # 强制设为前台窗口（配合附加线程输入可成功）
    finally:                     # 无论成功失败都要恢复
        if attached:             # 若之前附加了输入线程
            user32.AttachThreadInput(cur, fg_thread, False)  # 解除附加，避免影响其他窗口


def _win_user32():
    """获取 user32 句柄，非 Windows 环境直接报错"""
    try:                         # 尝试加载 user32
        import ctypes            # Windows API 调用库
        return ctypes.windll.user32, ctypes  # 返回 (user32 接口, ctypes 模块)
    except Exception as e:       # 非 Windows 环境加载失败
        raise RuntimeError("当前环境不是 Windows，无法使用 PostMessage 按键。请在 Windows 上运行本脚本。")  # 抛出明确错误


def find_game_window():
    """按标题关键词找游戏窗口，返回 hwnd 或 None"""
    user32, ctypes = _win_user32()  # 获取 user32 API
    found = []                  # 存放匹配到的窗口句柄列表

    def cb(hwnd, _):            # 回调函数（EnumWindows 对每个窗口调用）
        buf = ctypes.create_unicode_buffer(512)  # 创建 512 宽字符缓冲区存窗口标题
        user32.GetWindowTextW(hwnd, buf, 512)    # 读取窗口标题到缓冲区
        if TITLE_KEY in buf.value and user32.IsWindowVisible(hwnd):  # 标题含关键词且窗口可见
            found.append(hwnd)  # 记录该窗口句柄
        return True             # 返回 True 继续枚举下一个窗口

    proto = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)  # 定义回调函数签名（bool 返回值，两个指针参数）
    user32.EnumWindows(proto(cb), 0)  # 枚举所有顶层窗口，对每个调用 cb
    return found[0] if found else None  # 返回第一个匹配窗口；没有则返回 None


def send_key(hwnd, vk, down):
    """PostMessage 直发 WM_KEYDOWN / WM_KEYUP"""
    user32, ctypes = _win_user32()  # 获取 user32 API
    scan = user32.MapVirtualKeyW(vk, 0) & 0xFF  # 把虚拟键码映射为扫描码（取低 8 位）
    lparam = (scan << 16) | 1     # 构造 lParam：高 16 位=扫描码，低 16 位=重复次数1
    if not down:                  # 如果是松开按键
        lparam |= (1 << 30) | (1 << 31)  # 加 30 位（previous key state=曾按下）和 31 位（transition state=正在松开）
    user32.PostMessageW(hwnd, WM_KEYDOWN if down else WM_KEYUP, vk, lparam)  # 异步投递按键消息到窗口


def hold_key(hwnd, vk, seconds):
    """按住某键 seconds 秒后松开"""
    send_key(hwnd, vk, True)   # 发送按下消息
    time.sleep(seconds)        # 持续按住指定秒数
    send_key(hwnd, vk, False)  # 发送松开消息


def tap_key(hwnd, vk):
    """短按某键（按下立即松开）"""
    send_key(hwnd, vk, True)   # 发送按下消息
    time.sleep(0.08)           # 极短延时（80ms）保证游戏能识别按下
    send_key(hwnd, vk, False)  # 发送松开消息


def press_esc():
    """按 ESC 关闭游戏内活动引导弹窗（如「3分钟直升15万」）。
    方案：检测弹窗标题模板 → 检测到则「置前台 + keybd_event 真实键盘 ESC」→ 复查是否关闭，
    最多循环 5 次；弹窗消失或不存在则结束。
    实测：adb keyevent / PostMessage 对活动弹窗无效（游戏区分按键来源）；
    模拟器是管理员 Qt 窗口，必须「管理员进程 + 置前台 + keybd_event」才有效
    （脚本已通过 ensure_admin 提权，本函数在管理员权限下运行）。"""
    hwnd = find_game_window()            # 查找游戏窗口句柄
    if hwnd is None:                     # 找不到游戏窗口
        print("[按键] 未找到游戏窗口，无法按 ESC")  # 打印提示
        return                           # 直接返回（跳过）
    user32, ctypes = _win_user32()       # 获取 user32 API 和 ctypes（keybd_event 用）
    for i in range(5):                   # 最多循环 5 次（每次按一次 ESC 后复查）
        frame = capture_hdmi()           # 截取当前画面（检测弹窗是否还在）
        if frame is None:                # 截图失败
            time.sleep(1)                # 等 1s
            continue                     # 继续循环
        score, center = detect_button(frame, TEMPLATE_POPUP)  # 检测活动弹窗标题模板
        if score is None or score < CONFIRM_TH or not center:  # 弹窗不存在或已关闭
            print("[按键] 活动弹窗已关闭或未出现")  # 打印结果
            return                       # 结束
        print(f"[按键] 检测到活动弹窗（相似度 {score:.3f}），第 {i+1} 次按 ESC…")  # 打印按键日志
        force_foreground(hwnd)           # 强制把游戏窗口置为前台（Qt 窗口激活后才接收键盘）
        time.sleep(0.3)                  # 等 0.3s 让窗口完成激活
        user32.keybd_event(0x1B, 0, 0, 0)  # keybd_event 按下 ESC（虚拟键码 0x1B=27）
        time.sleep(0.12)                 # 极短间隔（120ms）
        user32.keybd_event(0x1B, 0, 2, 0)  # keybd_event 松开 ESC（KEYEVENTF_KEYUP=2）
        time.sleep(1.0)                  # 等 1s 让 ESC 生效后再复查
    print("[按键] 连续按 5 次 ESC 弹窗仍未关闭，放弃处理")  # 打印放弃日志


def scroll_wheel(hwnd, delta, x=960, y=540):
    """PostMessage 直发滚轮（模拟器游戏面板滚动）。
    delta>0 向上滚（列表滚到顶部），delta<0 向下滚（列表往下看）。
    x,y 为窗口内光标位置（模拟器按窗口内坐标处理滚轮）。"""
    user32, ctypes = _win_user32()  # 获取 user32 API
    wparam = (int(delta) << 16) & 0xFFFF0000  # 滚轮 delta 放入 wParam 高 16 位（低位标志位=0）
    lparam = ((int(y) & 0xFFFF) << 16) | (int(x) & 0xFFFF)  # lParam：高 16 位=y 坐标，低 16 位=x 坐标
    user32.PostMessageW(hwnd, WM_MOUSEWHEEL, wparam, lparam)  # 异步投递滚轮消息


def scroll_to_top(hwnd, seconds=5.0):
    """连续向上滚 seconds 秒（滚到最上面）。每 50ms 一档。"""
    end = time.time() + seconds  # 计算结束时间点
    while time.time() < end:     # 未到结束时间则持续滚动
        scroll_wheel(hwnd, 120)  # 向上滚一档（delta=120 标准一档）
        time.sleep(0.05)         # 每档间隔 50ms


def scroll_down_slow(hwnd, step_delta=-120, step_wait=1.0):
    """向下滚一档（慢慢往下看），返回后由调用方检测「可刷新」。"""
    scroll_wheel(hwnd, step_delta)  # 向下滚一档（delta=-120）
    time.sleep(step_wait)           # 等待界面稳定（默认 1s）


# ---------------- 截图（adb → 自动探测设备与游戏 display） ----------------
def find_adb():
    """在应用宝安装目录中查找 adb.exe，找不到则退回系统 PATH 中的 adb"""
    cands = (glob.glob(r"C:\Program Files\Tencent\Androws\Application\*\adb.exe") +  # 应用宝主目录通配查找
             glob.glob(r"C:\Program Files\Tencent\AndrowsData\Component\Androws\adb.exe"))  # 数据组件目录查找
    return cands[0] if cands else "adb"  # 返回找到的第一个路径；都没有则用 PATH 里的 adb


def adb_base():
    """返回 adb 命令前缀（含 -s 设备名，自动探测）"""
    global ADB_DEVICE           # 声明修改全局设备名（探测结果缓存）
    if ADB_DEVICE is None:      # 尚未探测过设备
        ADB_DEVICE = ""         # 先默认空（用 adb 默认连接的唯一设备）
        try:                    # 尝试执行 adb devices
            r = subprocess.run([find_adb(), "devices"], capture_output=True,  # 执行 adb devices 列出设备
                               text=True, timeout=20)  # 文本输出、20s 超时
            for line in r.stdout.splitlines()[1:]:     # 逐行解析输出（跳过表头 "List of devices"）
                parts = line.split()                    # 按空白切分该行
                if len(parts) >= 2 and parts[1] == "device":  # 第二列是 device（已授权连接）
                    ADB_DEVICE = parts[0]               # 记录设备名（如 emulator-5554）
                    break                               # 只取第一个可用设备
        except Exception:       # adb 执行失败（未安装等）
            pass                # 忽略，保持默认空设备
        print(f"[adb] 设备：{ADB_DEVICE or '默认'}")     # 打印探测到的设备名
    return [find_adb()] + (["-s", ADB_DEVICE] if ADB_DEVICE else [])  # 返回完整前缀：adb 路径 + (-s 设备名)


def probe_display():
    """探测哪个 display 能截到非黑屏画面（游戏屏），返回 display 值或 None"""
    global DISPLAY_ID           # 声明修改全局 display 编号（探测结果缓存）
    base = adb_base()           # 获取 adb 命令前缀
    probe = os.path.join(tempfile.gettempdir(), "_dnfm_probe.png")  # 探测截图的本机暂存路径
    for d in DISPLAY_CANDIDATES:  # 按优先级逐个尝试候选 display
        cmd = base + ["shell", "screencap"] + (["-d", d] if d else []) + ["-p", TMP_REMOTE]  # 构造截屏命令（-d 指定 display）
        try:                    # 尝试执行截屏
            r = subprocess.run(cmd, capture_output=True, timeout=60)  # 执行截屏命令
            if r.returncode != 0:  # 截屏命令失败（该 display 不存在）
                continue        # 尝试下一个候选
            subprocess.run(base + ["pull", TMP_REMOTE, probe],  # 把设备上的截图拉到本机
                           capture_output=True, timeout=60)
            img = cv2.imread(probe)  # 用 OpenCV 读取截图
            if img is None or img.std() < 5:   # 读失败或画面标准差<5（黑屏）
                continue        # 黑屏/坏图跳过，尝试下一个
            DISPLAY_ID = d      # 该 display 能截到有效画面 → 记录
            print(f"[adb] 游戏 display 已探测：{d or '默认'}"  # 打印探测结果
                  f"（画面 {img.shape[1]}x{img.shape[0]}）")  # 附画面宽高
            return d            # 返回该 display 编号
        except Exception:       # 任何异常（超时/IO 错误）
            continue            # 尝试下一个候选
    DISPLAY_ID = None           # 全部候选都失败 → 置空
    print("[adb] 未探测到游戏画面 display，将使用默认截图")  # 打印提示（可能游戏未运行）
    return None                 # 返回 None 表示用默认 display


# ---------------- 窗口尺寸记忆与校验 ----------------
def load_config():
    """读取 config.json（保存上次窗口尺寸等），文件不存在/解析失败返回空字典"""
    try:                           # 尝试读取配置文件
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:  # 以 UTF-8 打开
            return json.load(f)    # 解析 JSON 返回配置字典
    except Exception:              # 文件不存在或内容损坏
        return {}                  # 返回空字典（按首次运行处理）


def save_window_size(w, h, cw=None, ch=None):
    """把当前窗口尺寸写入 config.json（hdmi=adb 截图画面的分辨率，client=Windows 窗口客户区）"""
    cfg = load_config()            # 读现有配置（保留其他已有字段）
    cfg["window_size"] = {         # 写入窗口尺寸记录
        "hdmi_w": int(w),          # HDMI/adb 截图画面的宽度
        "hdmi_h": int(h),          # HDMI/adb 截图画面的高度
        "client_w": int(cw) if cw else None,  # 游戏窗口客户区宽度（调整窗口时用）
        "client_h": int(ch) if ch else None,  # 游戏窗口客户区高度
    }
    try:                           # 尝试写入配置文件
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:  # 以 UTF-8 写文件
            json.dump(cfg, f, ensure_ascii=False, indent=2)  # 序列化为可读 JSON
    except Exception as e:         # 写入失败（磁盘只读等）
        print(f"[窗口] 保存配置失败：{e}")  # 打印错误但不中断主流程


def get_client_size(hwnd):
    """获取窗口客户区尺寸，返回 (宽, 高)；失败返回 (None, None)"""
    try:                           # 尝试获取
        user32, ctypes = _win_user32()  # 获取 user32 API 与 ctypes
        import ctypes.wintypes    # 显式导入 wintypes（Python 延迟加载，不显式导入会报无此属性）
        r = ctypes.wintypes.RECT()  # 客户区矩形结构
        user32.GetClientRect(hwnd, ctypes.byref(r))  # 读取客户区（相对窗口左上角）
        return r.right, r.bottom   # 返回宽、高
    except Exception:              # 调用失败（句柄失效等）
        return None, None          # 返回空


def set_client_size(hwnd, cw, ch):
    """把窗口客户区调整为指定尺寸（外框=客户区+边框差，SetWindowPos 调整），返回是否成功"""
    try:                           # 尝试调整
        user32, ctypes = _win_user32()  # 获取 user32 API 与 ctypes
        import ctypes.wintypes    # 显式导入 wintypes（同上，SetWindowPos 用 RECT 结构）
        wr = ctypes.wintypes.RECT()  # 窗口外框矩形
        cr = ctypes.wintypes.RECT()  # 窗口客户区矩形
        user32.GetWindowRect(hwnd, ctypes.byref(wr))   # 读外框（屏幕坐标）
        user32.GetClientRect(hwnd, ctypes.byref(cr))   # 读客户区（相对坐标）
        bw = (wr.right - wr.left) - cr.right   # 左右边框+滚动条宽度差
        bh = (wr.bottom - wr.top) - cr.bottom  # 上下边框+标题栏高度差
        # SetWindowPos：保持原位置与 Z 序，只改窗口外框尺寸（客户区 + 边框差 = 目标）
        ok = user32.SetWindowPos(hwnd, 0, wr.left, wr.top, cw + bw, ch + bh,
                                 0x0004 | 0x0010)  # SWP_NOMOVE=不移动 | SWP_NOZORDER=不变Z序
        return bool(ok)            # 返回是否设置成功
    except Exception:              # 调用失败
        return False               # 返回失败


def ensure_window_size():
    """启动前校验游戏窗口尺寸：
    首次运行 → 记录当前 HDMI 画面尺寸 + 窗口客户区；
    之后每次运行 → 截图对比，不一致则自动调整窗口客户区到记录值并验证；
    自动调整无效 → 提示用户手动调整（等待 60s），仍无效则退出脚本（避免模板失配跑废）。"""
    cfg = load_config()            # 读取上次记录
    saved = cfg.get("window_size")  # 上次保存的窗口尺寸（dict 或 None）
    frame = capture_hdmi()         # 截取当前画面（同时触发 display 探测）
    if frame is None:              # 截图失败（模拟器未就绪）
        print("[窗口] 无法截图，跳过窗口尺寸校验（后续流程会报 ADB 错误）")  # 打印提示
        return                     # 跳过校验，交给后续流程处理
    if frame.std() < 5:            # 画面标准差极低 = 黑屏（HDMI 未连接/模拟器未正常显示）
        print("[窗口] 模拟器画面为黑屏（HDMI 输出异常/模拟器未正常显示），请打开模拟器窗口并确认游戏画面后重新运行。")  # 打印黑屏提示
        msgbox("模拟器画面黑屏：请打开模拟器窗口、确认游戏画面正常显示后重新运行脚本。", "dnfm-auto 挂机")  # 弹窗明确告知原因
        sys.exit(1)                # 退出（避免黑屏状态下继续跑导致模板全失配）
    h, w = frame.shape[0], frame.shape[1]  # 当前 HDMI 画面尺寸
    hwnd = find_game_window()      # 找游戏窗口（调整尺寸需要句柄）
    cw = ch = None                 # 当前客户区尺寸（默认未知）
    if hwnd is not None:           # 找到游戏窗口
        cw, ch = get_client_size(hwnd)  # 读取客户区尺寸
    if saved is None:              # 首次运行：没有历史记录
        print(f"[窗口] 首次运行，记录窗口尺寸：HDMI {w}x{h}，客户区 {cw or '?'}x{ch or '?'}")  # 打印记录
        save_window_size(w, h, cw, ch)  # 写入 config.json
        return                     # 直接返回（无需校验）
    sw, sh = saved.get("hdmi_w"), saved.get("hdmi_h")  # 上次记录的 HDMI 尺寸
    if not sw or not sh:           # 记录缺失（配置损坏）
        print(f"[窗口] 配置缺失尺寸记录，重新记录当前 {w}x{h}")  # 打印提示
        save_window_size(w, h, cw, ch)  # 重新记录当前值
        return
    # 尺寸对比（±2% 容差，微小边框差异不影响模板匹配）
    if abs(w - sw) / sw <= SIZE_TOLERANCE and abs(h - sh) / sh <= SIZE_TOLERANCE:
        print(f"[窗口] 尺寸一致（HDMI {w}x{h}，记录 {sw}x{sh}）")  # 一致则打印确认
        return
    # 尺寸不一致 → 尝试自动调整窗口
    print(f"[窗口] 尺寸不一致：当前 HDMI {w}x{h}，记录 {sw}x{sh}，尝试调整游戏窗口…")
    if hwnd is None:               # 找不到游戏窗口句柄
        print(f"[窗口] 未找到游戏窗口，无法自动调整。请手动把模拟器窗口调回 {sw}x{sh} 后重新运行。")
        sys.exit(1)                # 退出（避免带错尺寸跑图导致模板失配）
    target_cw, target_ch = saved.get("client_w"), saved.get("client_h")  # 记录的目标客户区
    if not target_cw or not target_ch:  # 记录里没有客户区（旧配置）
        print(f"[窗口] 配置缺少客户区记录，自动记录当前尺寸（HDMI {w}x{h}，客户区 {cw or '?'}x{ch or '?'}）。")
        print(f"[窗口] 注意：若 HDMI 分辨率与模板基准 1360x764 差异较大，模板匹配可能失效，"
              f"请把模拟器分辨率调回 1360x764 后再运行（模板按该分辨率裁剪）。")
        save_window_size(w, h, cw, ch)  # 记录当前尺寸（下次运行按新尺寸校验）
        return                         # 继续运行（不再直接退出）
    if not set_client_size(hwnd, target_cw, target_ch):  # 调整窗口客户区失败（可能权限不足被 UIPI 拦截）
        print("[窗口] 自动调整窗口失败（脚本以管理员运行时会自动调整成功），5s 后直接运行…")
    else:                          # 调整指令已发出
        print(f"[窗口] 已调整窗口客户区至 {target_cw}x{target_ch}，等待 5s 生效…")
    time.sleep(5)                  # 固定等 5s 让窗口刷新，不再校验屏幕尺寸（用户要求）
    return                         # 直接返回继续主流程


def capture_hdmi():
    """截取游戏完整画面，返回 BGR ndarray 或 None
    截图失败时自动重新探测 display（模拟器 display 可能漂移）"""
    global DISPLAY_ID           # 声明修改全局 display（失败时要重置探测）
    for attempt in range(2):    # 最多尝试 2 次（第 2 次强制重新探测 display）
        if DISPLAY_ID is None:  # 尚无 display 记录
            probe_display()     # 先探测可用 display
        try:                    # 尝试截图
            base = adb_base()   # 获取 adb 命令前缀
            cmd = base + ["shell", "screencap"]  # 基础截屏命令
            if DISPLAY_ID is not None:  # 已探测到 display
                cmd += ["-d", DISPLAY_ID]  # 显式指定 display（防漂移截错屏）
            cmd += ["-p", TMP_REMOTE]  # 输出到设备固定路径
            subprocess.run(cmd, capture_output=True, timeout=60)  # 执行截屏
            subprocess.run(base + ["pull", TMP_REMOTE, TMP_LOCAL],  # 拉到本机临时路径
                           capture_output=True, timeout=60)
            img = cv2.imread(TMP_LOCAL)  # 读取截图
            if img is not None:  # 读取成功
                return img      # 返回画面数组
        except Exception as e:  # 截图异常（adb 断开等）
            print(f"截图异常：{e}")  # 打印异常信息
        # 失败 → 强制重新探测 display 再试一次
        DISPLAY_ID = None       # 清空 display 记录
        probe_display()         # 重新探测（模拟器 display 可能漂移了）
    return None                 # 两次都失败 → 返回 None


# ---------------- 检测按钮（多模板通用） ----------------
def detect_button(frame, template_path, roi=None):
    """多尺度模板匹配，返回 (相似度, 中心坐标) 或 (None, None)
    roi=(x1,y1,x2,y2) 时只在指定区域搜索（避免误匹配）"""
    tmpl = cv2.imread(template_path)  # 读取模板图
    if tmpl is None:            # 模板文件不存在
        return None, None       # 返回空结果
    ox, oy = 0, 0               # ROI 偏移量（原图坐标 = ROI 内坐标 + 偏移）
    search = frame              # 默认在整个画面搜索
    if roi is not None:         # 指定了搜索区域
        x1, y1, x2, y2 = roi    # 解包 ROI 边界
        x2, y2 = min(x2, frame.shape[1]), min(y2, frame.shape[0])  # 限制边界不超过画面尺寸
        if x2 <= x1 or y2 <= y1:  # ROI 无效（宽度或高度为 0）
            return None, None   # 直接返回空
        ox, oy = x1, y1         # 记录偏移量
        search = frame[y1:y2, x1:x2]  # 截取 ROI 子图作为搜索范围
    best_val, best_loc, best_scale = 0.0, None, None  # 记录最优相似度/位置/缩放
    for scale in SCALES:        # 遍历所有缩放比例
        tw = max(8, int(tmpl.shape[1] * scale))  # 缩放后的模板宽度（最小 8px）
        th = max(8, int(tmpl.shape[0] * scale))  # 缩放后的模板高度（最小 8px）
        if tw > search.shape[1] or th > search.shape[0]:  # 模板大于搜索图（无意义）
            continue            # 跳过该缩放
        resized = cv2.resize(tmpl, (tw, th))  # 缩放模板到当前尺寸
        result = cv2.matchTemplate(search, resized, cv2.TM_CCOEFF_NORMED)  # 归一化相关系数匹配
        _, max_val, _, max_loc = cv2.minMaxLoc(result)  # 取最匹配的位置和值
        if max_val > best_val:  # 当前缩放匹配度更高
            best_val, best_loc, best_scale = max_val, max_loc, scale  # 更新最优结果
    if best_loc is None:        # 所有缩放都没匹配到（搜索图太小等）
        return None, None       # 返回空结果
    cx = ox + best_loc[0] + int(tmpl.shape[1] * best_scale) // 2  # 计算匹配框中心 x（含 ROI 偏移）
    cy = oy + best_loc[1] + int(tmpl.shape[0] * best_scale) // 2  # 计算匹配框中心 y（含 ROI 偏移）
    return float(best_val), (cx, cy)  # 返回 (相似度, 中心像素坐标)


def challenge_roi(frame):
    """「再次挑战」按钮搜索区域：结算界面右上角按钮列（实测 (0.886w,0.137h)）。
    城镇「返回城镇」也在该区域内，但红字白底模板对返回城镇实测 0.503 < 0.60 不会误判。"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    return (int(w * 0.80), int(h * 0.05), w, int(h * 0.40))  # 右上角 80%-100% 宽 × 5%-40% 高


def reward_roi_top(frame):
    """「领奖结算」按钮位置1（仅领奖结算界面，实测按钮 @y0.126h）搜索区域。
    排除城镇「返回城镇」（y 0.15-0.19h）——实测本 ROI 内城镇匹配 0.551 < REWARD_TH 安全"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    return (int(w * 0.80), int(h * 0.08), w, int(h * 0.17))  # 右上角 80%-100% 宽 × 8%-17% 高


def reward_roi_bottom(frame):
    """「领奖结算」按钮位置2（再次挑战+领奖结算界面，实测按钮 @y0.226h）搜索区域。
    排除城镇「返回城镇」（y 0.15-0.19h）——实测本 ROI 内城镇匹配 0.575 < REWARD_TH 安全"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    return (int(w * 0.80), int(h * 0.18), w, int(h * 0.30))  # 右上角 80%-100% 宽 × 18%-30% 高


def detect_reward(frame):
    """检测「领奖结算」：两个可能位置（y0.126h 单按钮 / y0.226h 双按钮）都搜索，
    返回达标且更优的 (相似度, 中心)；都不达标返回 (None, None)"""
    best = (None, None)                      # 记录最优结果
    for roi in (reward_roi_top(frame), reward_roi_bottom(frame)):  # 遍历两个可能位置区域
        s, c = detect_button(frame, TEMPLATE_REWARD, roi=roi)  # 在单个 ROI 内检测
        if s is not None and s >= REWARD_TH and c:  # 匹配达标（阈值 0.70）
            if best[0] is None or s > best[0]:      # 比当前最优更好
                best = (s, c)                      # 更新最优结果
    return best                              # 返回最优 (相似度, 中心)


def confirm_reward(frame):
    """连续两次检测确认「领奖结算」（两位置都试，防抖动/防误触），返回 (相似度, 中心)"""
    score, center = detect_reward(frame)     # 第一次检测（两个位置）
    if score is not None and center:         # 第一次达标
        time.sleep(0.5)                      # 等 0.5s 再复查
        frame2 = capture_hdmi()              # 再截一张新画面
        if frame2 is not None:               # 截图成功
            score2, center2 = detect_reward(frame2)  # 第二次检测（同两位置）
            if score2 is not None and center2:       # 两次都达标才算确认
                return score2, center2       # 返回第二次的结果
    return None, None                        # 两次不一致 → 视为误匹配


def detect_challenge(frame):
    """检测「再次挑战」，返回 (相似度, 中心)"""
    return detect_button(frame, TEMPLATE_PATH, roi=challenge_roi(frame))  # 限定区域检测（排除右上角返回城镇误匹配）


def confirm_button(frame, template_path, label, roi=None):
    """连续两次检测确认按钮（防主城误触），返回 (相似度, 中心) 或 (None, None)
    roi=(x1,y1,x2,y2) 时只在指定区域搜索（避免误匹配）"""
    score, center = detect_button(frame, template_path, roi=roi)  # 第一次匹配（可选限定区域）
    if score is not None and score >= MATCH_TH and center:  # 第一次匹配达标
        time.sleep(0.5)         # 等 0.5s 再复查（防抖动/防误触）
        frame2 = capture_hdmi() # 再截一张新画面
        if frame2 is not None:  # 截图成功
            score2, center2 = detect_button(frame2, template_path, roi=roi)  # 第二次匹配（同区域）
            if score2 is not None and score2 >= MATCH_TH and center2:  # 两次都达标才算确认
                return score2, center2  # 返回第二次的匹配结果
    return None, None           # 两次不一致 → 视为误匹配


# ---------------- 三个阶段 ----------------
def stage1_forward(hwnd):
    """阶段1：循环执行「后退0.2s → 前进2s → 斜上(→+↑)0.5s → 斜下(→+↓)1.0s」，
    累计 ROUND_SECONDS=22s 后结束（之后进入阶段2检测）。"""
    t0 = time.time()            # 记录开始时间
    while time.time() - t0 < ROUND_SECONDS:  # 未跑满 22s 就继续循环
        # 1) 先向后跑 BACK_STEP 秒（← 后退一小段，避免贴墙/卡点）
        send_key(hwnd, VK["left"], True)   # 按住 ←（向后跑）
        time.sleep(BACK_STEP)              # 持续 0.2s
        send_key(hwnd, VK["left"], False)  # 松开 ←
        # 2) 再向前直跑 FWD_STEP 秒（按住 →）
        send_key(hwnd, VK["right"], True)  # 按住 →（开始前进）
        time.sleep(FWD_STEP)               # 持续 2s
        # 3) 同时按住 ↑ + → 斜上跑 DIAG_UP_STEP 秒（→ 保持按住）
        send_key(hwnd, VK["up"], True)     # 按住 ↑
        time.sleep(DIAG_UP_STEP)           # 持续 0.5s
        send_key(hwnd, VK["up"], False)    # 松开 ↑
        # 4) 同时按住 ↓ + → 斜下跑 DIAG_DOWN_STEP 秒（→ 保持按住）
        send_key(hwnd, VK["down"], True)   # 按住 ↓
        time.sleep(DIAG_DOWN_STEP)         # 持续 1.0s
        send_key(hwnd, VK["down"], False)  # 松开 ↓
        send_key(hwnd, VK["right"], False)  # 松开 →（结束本轮前进）
    print(f"[跑图] 完成一轮（{ROUND_SECONDS:.0f}s：退0.2→进2→斜上0.5→斜下1.0 循环）")  # 打印跑图完成日志


def stage2_wait_challenge(hwnd):
    """阶段2：检测「再次挑战」或「领奖结算」；
    都没有 → 前进 MOVE_STEP 秒 → 再检测。
    返回 "challenge"（再次挑战）/ "reward"（领奖结算）/ "restart"（超时未检测到，重新跑图）"""
    n = 0                       # 连续截图失败计数
    t_start = time.time()       # 记录本阶段检测开始时间（用于 3 分钟超时判断）
    while True:                 # 无限循环直到检测到按钮
        if time.time() - t_start > STAGE2_TIMEOUT:  # 超过 3 分钟仍未检测到任何按钮
            print(f"[检测] 超过 {STAGE2_TIMEOUT:.0f}s 未检测到「再次挑战」/「领奖结算」，提示音后重新跑图…")  # 打印超时日志
            beep(True)          # 播放提示音（提醒用户注意）
            time.sleep(0.4)     # 间隔 0.4s
            beep(True)          # 再响一声（双响提示更明显）
            return "restart"    # 返回重启标志（主循环收到后从跑图重新开始）
        frame = capture_hdmi()  # 截取当前画面
        if frame is not None:   # 截图成功
            n = 0               # 重置失败计数
            score, _ = detect_challenge(frame)  # 检测「再次挑战」
            if score is not None and score >= MATCH_TH:  # 匹配达标
                print(f"[检测] 发现「再次挑战」（相似度 {score:.3f}）")  # 打印发现日志
                return "challenge"  # 返回挑战标志
            rs, _ = confirm_reward(frame)  # 确认「领奖结算」（两个可能位置都检测，专用阈值 REWARD_TH）
            if rs is not None and rs >= REWARD_TH:  # 发现「领奖结算」（阈值 0.70，城镇误匹配 0.55-0.58 被排除）
                # 用户要求：发现「领奖结算」后，再复查有没有「再次挑战」
                #   有「再次挑战」→ 优先点「再次挑战」（继续打怪）；没有 → 点「领奖结算」
                print(f"[检测] 发现「领奖结算」（相似度 {rs:.3f}），复查「再次挑战」…")  # 打印复查日志
                recheck_hit = False  # 复查是否发现「再次挑战」
                for _ in range(RECHECK_ROUNDS):  # 复查最多 RECHECK_ROUNDS=10 次（画面动态变化，需等按钮稳定）
                    time.sleep(RECHECK_WAIT)  # 间隔 RECHECK_WAIT=2s 再查
                    frame2 = capture_hdmi()  # 重新截取画面
                    if frame2 is None:  # 截图失败
                        continue       # 继续下一次复查
                    score2, _ = detect_challenge(frame2)  # 复查「再次挑战」
                    if score2 is not None and score2 >= MATCH_TH:  # 复查发现再次挑战
                        print(f"[检测] 复查发现「再次挑战」（相似度 {score2:.3f}），优先点击「再次挑战」")  # 打印日志
                        recheck_hit = True  # 标记命中
                        break              # 跳出复查
                if recheck_hit:          # 复查到再次挑战
                    return "challenge"   # 返回挑战标志（走再次挑战流程）
                print("[检测] 复查 3 次均无「再次挑战」，点「领奖结算」")  # 打印日志
                return "reward"          # 返回领奖标志（走领奖结算流程）
        else:                   # 截图失败
            n += 1              # 失败计数 +1
            if n >= SHOT_FAIL_LIMIT:  # 连续失败达到上限
                raise RuntimeError(f"连续 {SHOT_FAIL_LIMIT} 次截图失败，可能模拟器/ADB 断开")  # 抛出异常终止
        hold_key(hwnd, VK["right"], MOVE_STEP)  # 继续前进 2 秒
        print(f"[检测] 未发现「再次挑战」/「领奖结算」，前进 {MOVE_STEP}s 后重试…")  # 打印重试日志


def adb_tap(x, y):
    """adb 触摸点击游戏画面坐标。
    优先显式指定 display（与截图同一屏，防模拟器 display 漂移导致点错屏）"""
    base = adb_base()           # 获取 adb 命令前缀
    args = [str(int(x)), str(int(y))]  # 点击坐标参数（转字符串）
    if DISPLAY_ID is not None:  # 已探测到 display
        r = subprocess.run(base + ["shell", "input", "-d", DISPLAY_ID, "tap"] + args,  # 带 -d 指定 display 点击
                           capture_output=True, timeout=30)
        if r.returncode == 0:   # 点击成功
            return              # 直接返回
    subprocess.run(base + ["shell", "input", "tap"] + args,  # 兜底：不带 display 点击
                   capture_output=True, timeout=30)


def adb_back():
    """adb 返回键（keyevent 4），用于关闭弹窗/界面返回上一级"""
    base = adb_base()           # 获取 adb 命令前缀
    subprocess.run(base + ["shell", "input", "keyevent", "4"],  # 模拟 Android 返回键
                   capture_output=True, timeout=30)


def adb_swipe(x1, y1, x2, y2, duration_ms=300):
    """adb 触摸滑动（模拟手指滚动）。
    x1,y1 -> x2,y2：向下滑(y2>y1)=列表向上滚（看顶部）；向上滑(y2<y1)=列表向下滚（看下面）"""
    base = adb_base()           # 获取 adb 命令前缀
    args = [str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration_ms))]  # 滑动起终点+时长参数
    if DISPLAY_ID is not None:  # 已探测到 display
        r = subprocess.run(base + ["shell", "input", "-d", DISPLAY_ID, "swipe"] + args,  # 带 display 滑动
                           capture_output=True, timeout=30)
        if r.returncode == 0:   # 滑动成功
            return              # 直接返回
    subprocess.run(base + ["shell", "input", "swipe"] + args,  # 兜底：不带 display 滑动
                   capture_output=True, timeout=30)


def adb_roll(dx=0, dy=10):
    """adb 滚轮滚动（input roll）。dy>0 向下滚（看下面），dy<0 向上滚（看顶部）。
    对挑战进度面板/角色列表有效。"""
    base = adb_base()           # 获取 adb 命令前缀
    args = [str(int(dx)), str(int(dy))]  # 滚动方向参数
    if DISPLAY_ID is not None:  # 已探测到 display
        subprocess.run(base + ["shell", "input", "-d", DISPLAY_ID, "roll"] + args,  # 带 display 滚动
                       capture_output=True, timeout=30)
    else:                       # 未探测到 display
        subprocess.run(base + ["shell", "input", "roll"] + args,  # 不带 display 滚动
                       capture_output=True, timeout=30)


def mouse_click(x, y):
    """真实鼠标点击游戏画面坐标（HDMI 像素坐标）。
    背景：adb tap 对模拟器 display 2 已失效（HDMI 断后恢复触摸注入坏）；
    模拟器窗口接收真实鼠标点击转安卓触摸（与手动点击等效）。
    坐标换算：HDMI 画面 (x,y) → 窗口客户区坐标（按比例）→ 屏幕坐标（ClientToScreen）。
    需要管理员权限（脚本已 ensure_admin 提权，UIPI 才放行）。"""
    hwnd = find_game_window()            # 查找游戏窗口句柄
    if hwnd is None:                     # 找不到游戏窗口
        print("[鼠标] 未找到游戏窗口，无法点击")  # 打印提示
        return False                     # 返回失败
    user32, ctypes = _win_user32()       # 获取 user32 API 和 ctypes
    frame = capture_hdmi()               # 截取当前画面（拿 HDMI 实际尺寸做换算）
    if frame is None:                    # 截图失败
        print("[鼠标] 无法截图，取消点击")  # 打印提示
        return False                     # 返回失败
    fw, fh = frame.shape[1], frame.shape[0]  # HDMI 画面宽高
    cw, ch = get_client_size(hwnd)       # 窗口客户区尺寸
    if not cw or not ch:                 # 客户区获取失败
        print("[鼠标] 无法获取窗口客户区，取消点击")  # 打印提示
        return False                     # 返回失败
    wx = int(x * cw / fw)                # HDMI 坐标 → 窗口客户区 x（按宽度比例）
    wy = int(y * ch / fh)                # HDMI 坐标 → 窗口客户区 y（按高度比例）
    force_foreground(hwnd)               # 强制置前台（鼠标点击需要窗口可接收输入）
    time.sleep(0.3)                      # 等 0.3s 让窗口激活
    import ctypes.wintypes               # 显式导入 wintypes（POINT 结构）
    pt = ctypes.wintypes.POINT(0, 0)     # 客户区原点结构
    user32.ClientToScreen(hwnd, ctypes.byref(pt))  # 客户区原点 → 屏幕坐标（含边框偏移）
    sx, sy = pt.x + wx, pt.y + wy        # 目标屏幕坐标 = 客户区原点 + 客户区内坐标
    user32.SetCursorPos(sx, sy)          # 移动鼠标到目标位置
    time.sleep(0.2)                      # 等 0.2s 让鼠标就位
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN 按下左键
    time.sleep(0.08)                     # 极短间隔（80ms）
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP 松开左键
    print(f"[鼠标] 点击 ({x},{y}) → 窗口 ({wx},{wy}) → 屏幕 ({sx},{sy})")  # 打印点击日志
    return True                          # 返回成功


def stage3_trigger_challenge(hwnd):
    """阶段3：检测到「再次挑战」→ 点击 → 0.5s 后检测「确认」弹框：
    有「确认」→ 点击确认 → 0.5s 后再检测：
        还有「确认」→ 继续点击确认（弹框未关，重复确认）
        没有「确认」→ 回到顶部重新检测「再次挑战」（若还在则再点，进入下一轮触发）
    直到「再次挑战」按钮消失（已进入副本）→ 结束阶段3"""
    while True:                 # 循环直到「再次挑战」按钮消失
        frame = capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s 重试
            continue            # 继续循环
        score, center = confirm_button(frame, TEMPLATE_PATH, "再次挑战", roi=challenge_roi(frame))  # 限定区域确认「再次挑战」
        if score is not None and score >= MATCH_TH and center:  # 确认达标
            cx, cy = center     # 取出按钮中心坐标
            print(f"[触发] 点击「再次挑战」（相似度 {score:.3f}，坐标 {cx},{cy}），0.5s 后查确认弹框…")  # 打印点击日志
            adb_tap(cx, cy)     # adb 点击按钮
            time.sleep(0.5)     # 等 0.5s 让确认弹框出现
            # 处理「确认」弹框：有「确认」→ 点确认 → 0.5s 复查；无「确认」→ 跳出（回顶部重新点再次挑战）
            confirm_times = 0    # 本次「再次挑战」已连续点击「确认」的次数
            while True:         # 确认弹框处理循环
                frame2 = capture_hdmi()  # 重新截图（检测确认按钮）
                if frame2 is None:       # 截图失败
                    time.sleep(1)        # 等 1s
                    continue             # 继续重试截图
                cs, cc = detect_button(frame2, TEMPLATE_CHALLENGE_CONFIRM)  # 全图检测「确认」按钮（红底白字）
                if cs is not None and cs >= CONFIRM_TH and cc:  # 检测到确认按钮
                    if confirm_times >= 5:  # 已连续点了 5 次「确认」仍存在 → 异常，不再点确认
                        print("[触发] 确认弹框已连续点击 5 次仍存在，跳出确认循环，直接重新点击「再次挑战」")  # 打印异常处理日志
                        break              # 强制跳出确认循环（回顶部重新点再次挑战）
                    confirm_times += 1     # 计数 +1
                    print(f"[触发] 检测到确认弹框「确认」（第 {confirm_times} 次，相似度 {cs:.3f}，坐标 {cc}），点击确认…")  # 打印确认点击日志
                    adb_tap(cc[0], cc[1])  # 点击确认按钮
                    time.sleep(0.5)        # 等 0.5s 后再检测是否还有确认
                    continue               # 回到确认循环：继续检测还有没有「确认」
                break            # 没有「确认」→ 跳出确认循环
            continue            # 回到顶部：重新检测「再次挑战」（若按钮还在则继续点）
        print("[触发] 「再次挑战」已消失，进入下一轮")  # 按钮消失（已进入副本）
        return                  # 结束阶段3


def stage3_reward_settle(hwnd):
    """领奖结算流程（分阶段状态机）：
    A. 找「领奖结算」→ 点击 → 5s → B
    B. 找「结算」（限画面底部）→ 点击 → 3s → C；未找到 → 回 A
    C. 找「确认」→ 点击 → 2s → D；未找到「确认」→ 回 B 重新点「结算」
    D. 找「返回城镇」→ 点击 → 2s 复查：消失 → 完成退出；仍在 → 继续点；
       未找到 → 等待重试
    返回 "done"（完成退出）或 None（放弃回跑图）。"""
    phase = "A"                 # 状态机当前阶段（A/B/C/D）
    max_try = 40                # 总尝试上限（防死循环）
    for _ in range(max_try):    # 在总上限内循环
        frame = capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        h = frame.shape[0]      # 画面高度（用于底部 ROI 计算）
        if phase == "A":        # 阶段A：找「领奖结算」按钮
            # A：找「领奖结算」（限右上角按钮列 + 专用阈值）→ 点击
            rs, rcenter = detect_reward(frame)  # 两个可能位置检测「领奖结算」
            if rs is not None and rs >= REWARD_TH and rcenter:  # 匹配达标（阈值 0.70）
                cx, cy = rcenter  # 取出中心坐标
                print(f"[结算A] 点击「领奖结算」（相似度 {rs:.3f}，坐标 {cx},{cy}），5s 后查结算…")  # 打印日志
                adb_tap(cx, cy)  # 点击按钮
                time.sleep(5.0)  # 等 5s 让结算界面出现
                phase = "B"     # 进入阶段B
                continue        # 继续循环
            time.sleep(2)       # 未找到 → 等 2s 再试
        elif phase == "B":      # 阶段B：找「结算」按钮
            # B：找「结算」按钮（底部区域，防顶部「物品结算」误匹配）→ 点击
            ss, scenter = detect_button(frame, TEMPLATE_SETTLE,
                                        roi=(0, int(h * 0.65), frame.shape[1], h))  # 只在画面底部 65%-100% 搜索
            if ss is not None and ss >= MATCH_TH and scenter:  # 匹配达标
                cx, cy = scenter  # 取出中心坐标
                print(f"[结算B] 点击「结算」按钮（相似度 {ss:.3f}，坐标 {cx},{cy}），3s 后查「确认」…")  # 打印日志
                adb_tap(cx, cy)  # 点击结算按钮
                time.sleep(3.0)  # 等 3s 让确认弹窗出现
                phase = "C"     # 进入阶段C
                continue        # 继续循环
            print("[结算B] 未找到「结算」按钮，回 A 继续点「领奖结算」")  # 打印回退日志
            phase = "A"         # 回到阶段A重新点领奖结算
            continue            # 继续循环
        elif phase == "C":      # 阶段C：找「确认」按钮
            # C：找「确认」→ 点击 → D；没有确认 → 回 B 重新点「结算」
            cs, ccenter = detect_button(frame, TEMPLATE_CONFIRM)  # 全图检测「确认」
            if cs is not None and cs >= CONFIRM_TH and ccenter:  # 匹配达标（用独立低阈值）
                cx, cy = ccenter  # 取出中心坐标
                print(f"[结算C] 点击「确认」按钮（相似度 {cs:.3f}，坐标 {cx},{cy}），2s 后查「返回城镇」…")  # 打印日志
                adb_tap(cx, cy)  # 点击确认按钮
                time.sleep(2.0)  # 等 2s 让返回城镇按钮出现
                phase = "D"     # 进入阶段D
                continue        # 继续循环
            print("[结算C] 未找到「确认」按钮，回 B 重新点「结算」")  # 打印回退日志
            phase = "B"         # 回到阶段B重新点结算
            continue            # 继续循环
        else:                   # 阶段D：找「返回城镇」按钮
            # D：找「返回城镇」→ 点击 → 2s 复查
            ts, tcenter = detect_button(frame, TEMPLATE_TOWN)  # 全图检测「返回城镇」
            if ts is not None and ts >= MATCH_TH and tcenter:  # 匹配达标
                cx, cy = tcenter  # 取出中心坐标
                print(f"[结算D] 点击「返回城镇」（相似度 {ts:.3f}，坐标 {cx},{cy}），2s 后复查…")  # 打印日志
                adb_tap(cx, cy)  # 点击返回城镇按钮
                time.sleep(2.0)  # 等 2s 让界面返回
                frame2 = capture_hdmi()  # 再截一张复查
                if frame2 is not None:  # 复查截图成功
                    ts2, _ = detect_button(frame2, TEMPLATE_TOWN)  # 再检测「返回城镇」
                    if ts2 is None or ts2 < MATCH_TH:  # 按钮已消失 → 说明已回城
                        print("[结算D] 「返回城镇」已消失，已回城，领奖完成")  # 打印完成日志
                        return "done"  # 返回完成标志
                    print(f"[结算D] 「返回城镇」仍在（相似度 {ts2:.3f}），继续点击…")  # 按钮还在 → 继续点
                    continue    # 继续循环（回到 D 再点）
                continue        # 复查截图失败 → 重试
            time.sleep(2)       # 未找到返回城镇 → 等 2s 再试
    print("[结算] 多次尝试未完成领奖，回到跑图流程")  # 超过总上限 → 打印放弃日志
    return None                 # 返回 None 表示放弃（回到跑图）


# ---------------- 邮箱领取 ----------------
def mail_claim():
    """返回城镇后邮箱领取：
    等 MAIL_WAIT_AFTER_TOWN 秒 → 检测「领取全部物品」（限底部）→ 点击；
    没有 → 检测「邮箱」图标（限底部按钮栏）→ 点击 → 2s 后复查。
    点「领取全部」后：检测「确认」（最多3轮，有则点）→
    点「返回邮箱」直到按钮消失（回到主页面）。
    返回 True（完成）或 False（多次尝试未完成）。"""
    print(f"[邮箱] 等待 {MAIL_WAIT_AFTER_TOWN:.0f}s（返回城镇缓冲）…")  # 打印等待日志
    time.sleep(MAIL_WAIT_AFTER_TOWN)  # 等 5s（让城镇界面稳定）
    claimed = False             # 是否已成功点过「领取全部物品」
    for i in range(MAIL_ROUNDS):  # 最多尝试 MAIL_ROUNDS=10 轮
        frame = capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            print(f"[邮箱] 截图失败，1s 后重试…")  # 打印重试日志
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        h, w = frame.shape[0], frame.shape[1]  # 画面高宽（用于底部 ROI）
        # 1) 检测「领取全部物品」（邮箱界面底部按钮行）→ 有则点击
        cs, cc = detect_button(frame, TEMPLATE_CLAIM,
                               roi=(0, int(h * 0.85), w, h))  # 只在画面底部 85%-100% 搜索
        if cs is not None and cs >= CLAIM_TH and cc:  # 匹配达标
            print(f"[邮箱] 点击「领取全部物品」（相似度 {cs:.3f}，坐标 {cc}），3s 后查「确认」…")  # 打印日志
            adb_tap(cc[0], cc[1])  # 点击领取全部按钮
            time.sleep(3.0)     # 等 3s 让领取完成/确认弹窗出现
            claimed = True      # 标记已领取
            break               # 跳出循环进入后续确认步骤
        # 2) 没有「领取全部」→ 检测「邮箱」图标（底部按钮栏）→ 点击
        ms, mc = detect_button(frame, TEMPLATE_MAIL,
                               roi=(0, int(h * 0.82), w, h))  # 只在画面底部 82%-100% 搜索
        if ms is not None and ms >= MAIL_TH and mc:  # 匹配达标
            print(f"[邮箱] 点击「邮箱」图标（相似度 {ms:.3f}，坐标 {mc}），2s 后查领取…")  # 打印日志
            adb_tap(mc[0], mc[1])  # 点击邮箱图标（打开邮箱界面）
            time.sleep(2.0)     # 等 2s 让邮箱界面打开
            continue            # 继续循环（下次检测领取按钮）
        print(f"[邮箱] 未检测到邮箱图标，2s 后重试…")  # 打印重试日志
        time.sleep(2)           # 等 2s 再试

    if not claimed:             # 10 轮都没点到领取全部
        print("[邮箱] 多次尝试未检测到「领取全部」，邮件领取未完成")  # 打印失败日志
        return False            # 返回失败

    # 步骤A：点击领取后出现的「确认」（最多 3 轮，无则跳过）
    confirmed = False           # 是否已点过确认
    for _ in range(3):          # 最多 3 轮
        frame = capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        ks, kc = detect_button(frame, TEMPLATE_MAIL_CONFIRM)  # 全图检测「确认」
        if ks is not None and ks >= MAIL_CONFIRM_TH and kc:  # 匹配达标
            print(f"[邮箱] 点击「确认」（相似度 {ks:.3f}，坐标 {kc}），2s 后查「返回邮箱」…")  # 打印日志
            adb_tap(kc[0], kc[1])  # 点击确认按钮
            time.sleep(2.0)     # 等 2s
            confirmed = True    # 标记已确认
            break               # 跳出循环
        print(f"[邮箱] 未检测到「确认」按钮（第 {_+1} 轮），2s 后重试…")  # 打印重试日志
        time.sleep(2)           # 等 2s 再试
    if not confirmed:           # 3 轮都没确认按钮
        print("[邮箱] 无「确认」弹框，跳过确认步骤")  # 打印跳过日志（部分邮件无确认）

    # 步骤B：点击「返回邮箱」直到消失（回到主页面）
    for j in range(MAIL_ROUNDS):  # 最多 MAIL_ROUNDS=10 轮
        frame = capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        h, w = frame.shape[0], frame.shape[1]  # 画面高宽（用于左上 ROI）
        bs, bc = detect_button(frame, TEMPLATE_MAIL_BACK,
                               roi=(0, 0, int(w * 0.30), int(h * 0.25)))  # 只在左上角区域搜索
        if bs is not None and bs >= MAIL_BACK_TH and bc:  # 匹配达标（还在邮箱界面）
            print(f"[邮箱] 点击「返回邮箱」（相似度 {bs:.3f}，坐标 {bc}），2s 后复查…")  # 打印日志
            adb_tap(bc[0], bc[1])  # 点击返回邮箱按钮
            time.sleep(2.0)     # 等 2s 让界面返回
            continue            # 继续循环（复查是否消失）
        print(f"[邮箱] 「返回邮箱」已消失，回到主页面 ✓")  # 按钮消失 → 已回主页面
        return True             # 返回完成

    print("[邮箱] 「返回邮箱」一直存在，未回到主页面")  # 超时未回 → 打印日志
    return False                # 返回失败


# ---------------- 切换角色 ----------------
def char_select_roi(frame):
    """「选角」按钮搜索区域：城镇左上角（真实按钮位置）"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    return (0, 0, int(w * 0.15), int(h * 0.25))  # 左上 15% 宽 × 25% 高


def panel_title_roi(frame):
    """「挑战进度」面板标题搜索区域：面板顶部中央"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    return (int(w * 0.35), 0, int(w * 0.70), int(h * 0.15))  # 顶部中央 35%-70% 宽


def panel_list_roi(frame):
    """面板角色列表搜索区域（找「可刷新」）：排除右上角标题区/左下底部按钮区"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    return (int(w * 0.05), int(h * 0.15), int(w * 0.95), int(h * 0.70))  # 中部 5%-95% 宽 × 15%-70% 高


def panel_start_roi(frame):
    """面板底部「开始游戏」按钮搜索区域"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    return (int(w * 0.60), int(h * 0.80), w, h)  # 右下角 60%-100% 宽 × 80%-100% 高


def start_btn_yellow(frame):
    """判断「开始游戏」按钮是否变黄（可点击）。
    双通道：① 面板底部 ROI 黄色像素占比 > 0.15；② 黄色模板匹配 >= 阈值。
    返回 (是否变黄, 点击坐标或 None, 诊断信息)。"""
    roi = panel_start_roi(frame)  # 获取按钮搜索区域
    crop = frame[roi[1]:roi[3], roi[0]:roi[2]]  # 截取该区域图像
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)  # 转 HSV 色彩空间（方便按色相筛选黄色）
    mask = cv2.inRange(hsv, (15, 80, 80), (45, 255, 255))  # 黄色像素掩码（色相15-45，饱和度/明度80+）
    ratio = float(mask.mean()) / 255.0  # 黄色像素占比（0~1）
    ys, yc = detect_button(frame, TEMPLATE_START_YELLOW, roi=roi)  # 黄色按钮模板匹配
    if ratio > 0.15:            # 黄色像素占比超过 15% → 按钮已变黄
        # 黄色像素多 → 按钮中心为点击目标（ROI 右侧 1/3 区域中央）
        cx = int(roi[0] + (roi[2] - roi[0]) * 0.80)  # x = ROI 左边界 + 80% 宽度
        cy = int((roi[1] + roi[3]) / 2)  # y = ROI 垂直中心
        return True, (cx, cy), (ratio, ys)  # 返回 (已变黄, 点击坐标, 诊断)
    if ys is not None and ys >= START_YELLOW_TH and yc:  # 黄色模板匹配达标
        return True, yc, (ratio, ys)  # 返回 (已变黄, 模板中心, 诊断)
    return False, None, (ratio, ys)  # 未变黄 → 返回 (False, None, 诊断)


def confirm_roi(frame):
    """点开始游戏后弹框「确认」搜索区域：屏幕中央（排除右上角误匹配）"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    return (int(w * 0.25), int(h * 0.35), int(w * 0.75), int(h * 0.75))  # 中央 25%-75% 宽 × 35%-75% 高


def char_switch():
    """切换角色：
    返回主页面等 CHAR_WAIT_AFTER_HOME 秒 → 点「选角」→ 出现「挑战进度」面板
    → 先慢慢往底部拖找「可刷新」行（最长 CHAR_SCROLL_DOWN_SECONDS=30s）
    → 点击该行 → 「开始游戏」变黄 → 点击开始游戏 → 10s 后检查「确认」→ 有则点击后退出
    → 30s 底部无可刷新 → 往上滚（最长 CHAR_SCROLL_UP_SECONDS=60s）边滚边找
    → 60s 仍无可刷新 → 退出到主页面 → 退出脚本
    → 点击「可刷新」行后未变黄 → 继续滚找下一个「可刷新」行（跳过已试行）
    返回 True=成功切换角色；False=无可刷新/面板未打开（可终止循环）。"""
    print(f"[选角] 等待 {CHAR_WAIT_AFTER_HOME:.0f}s（回主页缓冲）…")  # 打印等待日志
    time.sleep(CHAR_WAIT_AFTER_HOME)  # 等 2s（回主页后界面缓冲）
    # 1) 点「选角」
    opened_panel = False        # 面板是否已打开
    for i in range(10):         # 最多 10 轮
        frame = capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        ps, pc = detect_button(frame, TEMPLATE_CHALLENGE_PANEL)  # 检测「挑战进度」面板（已打开标志）
        if ps is not None and ps >= PANEL_TH and pc:  # 匹配达标 → 面板已打开
            print(f"[选角] 面板已打开（相似度 {ps:.3f}）")  # 打印日志
            opened_panel = True  # 标记已打开
            break               # 跳出循环
        ss, sc = detect_button(frame, TEMPLATE_CHAR_SELECT, roi=char_select_roi(frame))  # 检测「选角」按钮（左上角）
        if ss is not None and ss >= CHAR_SELECT_TH and sc:  # 匹配达标
            print(f"[选角] 点击「选角」（相似度 {ss:.3f} @{sc}），2s 后检查面板…")  # 打印日志
            adb_tap(sc[0], sc[1])  # 点击选角按钮
            time.sleep(2.0)     # 等 2s 让面板打开
            continue            # 继续循环（下次检测面板）
        print(f"[选角] 未检测到「选角」（第 {i+1} 轮），2s 后重试…")  # 打印重试日志
        time.sleep(2)           # 等 2s 再试
    if not opened_panel:        # 10 轮都没打开面板
        # 再确认一次
        frame = capture_hdmi()  # 最后截一张
        if frame is None:       # 截图失败
            print("[选角] 多次尝试未打开挑战进度面板")  # 打印失败日志
            return False        # 返回失败
        ps, pc = detect_button(frame, TEMPLATE_CHALLENGE_PANEL)  # 最后检测一次面板
        if ps is None or ps < PANEL_TH:  # 仍没面板
            print("[选角] 多次尝试未打开挑战进度面板")  # 打印失败日志
            return False        # 返回失败
    # 2) 先慢慢往底部拖（最长 CHAR_SCROLL_DOWN_SECONDS 秒），边拖边找「可刷新」行
    #    方向：手指从下往上拖 (600,750)->(600,300) = 看列表下面（底部）
    #    滚动范围限制在列表安全区（y 300-750），避开面板表头(205-255)防止拖动整个面板
    tried_rows = []             # 记录已尝试过的「可刷新」行的 y 坐标（避免重复点同一行）

    def _try_refresh_row(frame):
        """检测「可刷新」行 → 点击该行 → 检查开始游戏变黄 → 变黄则点开始游戏+确认。
        返回 True=已成功开始游戏；False=未变黄/无可刷新行/行已试过。"""
        rs, rc = detect_button(frame, TEMPLATE_REFRESHABLE, roi=panel_list_roi(frame))  # 在列表区检测「可刷新」
        if rs is None or rs < REFRESHABLE_TH or not rc:  # 未匹配到
            return False        # 返回未找到
        if any(abs(rc[1] - t) < 40 for t in tried_rows):  # 该行 y 已试过（差<40px 视为同一行）
            return False        # 跳过已试行
        h0, w0 = frame.shape[0], frame.shape[1]  # 画面高宽
        row_x = int(w0 * 0.25)   # 角色名列中心（x=25% 宽）
        row_y = rc[1]            # 可刷新所在行的 y
        tried_rows.append(row_y)  # 记录该行已尝试
        print(f"[选角] 点击「可刷新」行（相似度 {rs:.3f} @({row_x},{row_y})，已试 {len(tried_rows)} 行）…")  # 打印日志
        adb_tap(row_x, row_y)   # 点击该角色行（选中角色）
        time.sleep(2.0)         # 等 2s 让选中生效
        frame2 = capture_hdmi()  # 再截一张
        if frame2 is None:      # 截图失败
            return False        # 返回未变黄
        yellow, yc, (ratio, ys) = start_btn_yellow(frame2)  # 判断开始游戏是否变黄
        if not (yellow and yc):  # 未变黄 → 该行刷新不可用
            print(f"[选角] 该行未变黄（黄色占比 {ratio:.3f}/模板 {ys or 0:.3f}），继续滚找下一个「可刷新」…")  # 打印日志
            return False        # 返回未变黄（外层继续滚动）
        print(f"[选角] 「开始游戏」变黄（黄色占比 {ratio:.3f}/模板 {ys or 0:.3f} @{yc}），点击…")  # 打印日志
        adb_tap(yc[0], yc[1])   # 点击开始游戏按钮
        # 3) 等 10s 检查「确认」按钮：有则点击，5s 后退出；无则直接退出
        print(f"[选角] 等待 {CHAR_CONFIRM_WAIT:.0f}s 后检查「确认」按钮…")  # 打印等待日志
        time.sleep(CHAR_CONFIRM_WAIT)  # 等 10s 让游戏加载新角色
        frame3 = capture_hdmi()  # 截取画面
        if frame3 is not None:  # 截图成功
            cf, cc = detect_button(frame3, TEMPLATE_START_CONFIRM, roi=confirm_roi(frame3))  # 中央区域检测「确认」
            if cf is not None and cf >= START_CONFIRM_TH and cc:  # 匹配达标
                print(f"[选角] 检测到「确认」（相似度 {cf:.3f} @{cc}），点击…")  # 打印日志
                adb_tap(cc[0], cc[1])  # 点击确认按钮
                print(f"[选角] 等待 {CHAR_EXIT_WAIT:.0f}s 后退出脚本")  # 打印等待日志
                time.sleep(CHAR_EXIT_WAIT)  # 等 5s 后退出
            else:               # 没有确认按钮
                print(f"[选角] 未检测到「确认」（{cf or 0:.3f}），直接退出脚本")  # 打印日志
        print("[选角] 点击「开始游戏」成功，退出脚本")  # 打印成功日志
        return True             # 返回成功（切换完成）

    print(f"[选角] 慢慢往底部拖找「可刷新」（最长 {CHAR_SCROLL_DOWN_SECONDS:.0f}s）…")  # 打印开始日志
    t0 = time.time()            # 记录开始时间
    while time.time() - t0 < CHAR_SCROLL_DOWN_SECONDS:  # 30s 内持续
        frame = capture_hdmi()  # 截取当前画面
        if frame is not None and _try_refresh_row(frame):  # 截图成功且成功开始游戏
            return True         # 返回成功
        adb_swipe(600, 750, 600, 300, CHAR_DRAG_MS)  # 从下往上慢拖 3s（看列表底部）
        time.sleep(1.0)         # 停 1s 再检测
    # 4) 30s 底部无可刷新 → 往上滚（最长 60s），边滚边找
    print(f"[选角] 底部未发现「可刷新」，往上滚找（最长 {CHAR_SCROLL_UP_SECONDS:.0f}s）…")  # 打印开始日志
    t0 = time.time()            # 记录开始时间
    while time.time() - t0 < CHAR_SCROLL_UP_SECONDS:  # 60s 内持续
        frame = capture_hdmi()  # 截取当前画面
        if frame is not None and _try_refresh_row(frame):  # 截图成功且成功开始游戏
            return True         # 返回成功
        adb_swipe(600, 300, 600, 750, CHAR_DRAG_MS)  # 从上往下慢拖 3s（看列表顶部）
        time.sleep(1.0)         # 停 1s 再检测
    # 5) 60s 仍无可刷新 → 退出到主页面 → 退出脚本
    print("[选角] 往上滚仍未发现「可刷新」，退出到主页面…")  # 打印退出日志
    close_panel()               # 关闭面板回到主页面
    print("[选角] 已退出到主页面，无角色可切换，结束切换角色")  # 打印结束日志
    return False                # 返回失败（无可切换角色）


def close_panel():
    """关闭「挑战进度」面板回到主页面。
    拖动面板标题栏（实测有效）；拖动无效时再点右上角 ×。"""
    try:                        # 尝试关闭面板
        adb_swipe(1070, 200, 1070, 900, 2000)  # 在面板标题栏从上往下拖（关闭面板）
        time.sleep(2.0)         # 等 2s
        frame = capture_hdmi()  # 截取画面检查
        if frame is None:       # 截图失败
            return              # 无法检查直接返回
        s, _ = detect_button(frame, TEMPLATE_CHALLENGE_PANEL)  # 检测面板是否还在
        if s is not None and s >= PANEL_TH:  # 面板还在（拖动没关掉）
            adb_tap(1996, 123)  # 右上角 ×（备用关闭方式）
            time.sleep(2.0)     # 等 2s
    except Exception as e:      # 关闭过程异常
        print(f"[选角] 关闭面板异常：{e}")  # 打印异常（不影响主流程）


# ---------------- 分解装备 ----------------
def decompose_btn_roi(frame):
    """「分解」入口按钮搜索区域：背包界面右下角（实测 (2049,1137)）"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    return (int(w * 0.45), int(h * 0.70), w, h)  # 右下 45%-100% 宽 × 70%-100% 高


def decompose_go_roi(frame):
    """弹框内金黄「分解」按钮搜索区域：画面底部（实测 (1798,1044)）"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    return (int(w * 0.35), int(h * 0.55), w, h)  # 底部 35%-100% 宽 × 55%-100% 高


def decompose_popup_roi(frame):
    """分解弹窗确认按钮搜索区域：画面中央（弹窗区域）"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    return (int(w * 0.15), int(h * 0.20), int(w * 0.85), int(h * 0.85))  # 中央大部分区域


def decompose_title_roi(frame):
    """分解弹框标题栏搜索区域：画面顶部中央（实测 (1311,131)，排除背包界面右下角误匹配）"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    return (int(w * 0.20), 0, int(w * 0.80), int(h * 0.22))  # 顶部中央 20%-80% 宽


def at_town(frame):
    """判断是否在城镇主界面：选角/神秘商店 任一标志匹配即视为在城镇。
    不用邮箱模板（在背包界面误匹配 0.6+，会误判）。"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    s1, _ = detect_button(frame, TEMPLATE_CHAR_SELECT, roi=(0, 0, int(w * 0.30), int(h * 0.30)))  # 左上30%区域检测「选角」
    s2, _ = detect_button(frame, TEMPLATE_SHOP, roi=shop_icon_roi(frame))  # 顶部区域检测「神秘商店」
    return (s1 is not None and s1 >= 0.60) or (s2 is not None and s2 >= 0.60)  # 任一达标即视为城镇


def decompose_equip():
    """分解装备流程（邮件领取后调用）：
    1) 邮件完成 DECOMPOSE_WAIT_AFTER_MAIL 秒 → 点「背包」图标（主页右下角）
       → 检测「分解」按钮（背包界面标志）；没有 → 继续点背包（最多 DECOMPOSE_MAX_TRY 轮）
    2) 点「分解」按钮 → 检测「分解弹框」（分解标题栏）；没出 → 继续点分解
    3) 点弹框内金黄「分解」→ 检测「外层提示弹窗」（确认按钮 @DECOMPOSE_OUTER_CONFIRM）
       ；没出 → 继续点金黄分解
    4) 点外层确认 → 检测「高价值二次确认」（highvalue 模板）→ 点内层确认
    5) 检测「获得道具」弹窗（result 模板）→ 点确认
    6) 点 × 关闭分解弹框 → 点返回箭头回主页面
    返回 True（完成）或 False（多次尝试失败）。"""
    print(f"[分解] 等待 {DECOMPOSE_WAIT_AFTER_MAIL:.0f}s（邮件完成缓冲）…")  # 打印等待日志
    time.sleep(DECOMPOSE_WAIT_AFTER_MAIL)  # 等 2s（邮件流程结束后缓冲）
    # 1) 点「背包」图标 → 检测「分解」按钮（背包界面已打开）
    opened = False              # 背包界面是否已打开
    for i in range(DECOMPOSE_MAX_TRY):  # 最多 10 轮
        frame = capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        h, w = frame.shape[0], frame.shape[1]  # 画面高宽
        ds, dc = detect_button(frame, TEMPLATE_DECOMPOSE_BTN, roi=decompose_btn_roi(frame))  # 检测「分解」按钮（背包界面标志）
        if ds is not None and ds >= DECOMPOSE_TH and dc:  # 匹配达标 → 已在背包界面
            print(f"[分解] 背包界面已打开（检测到「分解」按钮 {ds:.3f} @{dc}）")  # 打印日志
            opened = True       # 标记已打开
            break               # 跳出循环
        bs, bc = detect_button(frame, TEMPLATE_BAG, roi=(0, int(h * 0.6), w, h))  # 底部检测「背包」图标
        if bs is not None and bs >= DECOMPOSE_TH and bc:  # 匹配达标
            print(f"[分解] 点击「背包」图标（{bs:.3f} @{bc}），1s 后检查…")  # 打印日志
            adb_tap(bc[0], bc[1])  # 点击背包图标（打开背包）
            time.sleep(1.0)     # 等 1s
            continue            # 继续循环（下次检测分解按钮）
        print(f"[分解] 未检测到「背包」图标（第 {i+1} 轮），1s 后重试…")  # 打印重试日志
        time.sleep(1)           # 等 1s 再试
    if not opened:              # 10 轮没打开背包
        print("[分解] 未能打开背包界面，跳过分解")  # 打印失败日志
        return False            # 返回失败
    # 2) 点「分解」按钮 → 检测分解弹框（分解标题栏，顶部中央 ROI）
    for i in range(DECOMPOSE_MAX_TRY):  # 最多 10 轮
        frame = capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        ts, tc = detect_button(frame, TEMPLATE_DECOMPOSE_TITLE, roi=decompose_title_roi(frame))  # 顶部检测分解标题栏
        if ts is not None and ts >= DECOMPOSE_TH and tc:  # 匹配达标 → 弹框已出现
            print(f"[分解] 分解弹框已出现（标题栏 {ts:.3f} @{tc}）")  # 打印日志
            break               # 跳出循环
        ds, dc = detect_button(frame, TEMPLATE_DECOMPOSE_BTN, roi=decompose_btn_roi(frame))  # 检测「分解」按钮
        if ds is not None and ds >= DECOMPOSE_TH and dc:  # 匹配达标
            print(f"[分解] 点击「分解」按钮（{ds:.3f} @{dc}），1s 后检查弹框…")  # 打印日志
            adb_tap(dc[0], dc[1])  # 点击分解按钮（打开分解弹框）
            time.sleep(1.0)     # 等 1s
            continue            # 继续循环
        print(f"[分解] 未检测到「分解」按钮（第 {i+1} 轮）…")  # 打印重试日志
        time.sleep(1)           # 等 1s 再试
    # 3) 点弹框内金黄「分解」→ 检测外层提示弹窗（确认按钮在 DECOMPOSE_OUTER_CONFIRM 附近）
    for i in range(DECOMPOSE_MAX_TRY):  # 最多 10 轮
        frame = capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        h, w = frame.shape[0], frame.shape[1]  # 画面高宽
        cs, cc = detect_button(frame, TEMPLATE_DECOMPOSE_CONFIRM, roi=decompose_popup_roi(frame))  # 中央检测「确认」
        if (cs is not None and cs >= DECOMPOSE_TH and cc  # 确认按钮匹配达标
                and abs(cc[1] - DECOMPOSE_OUTER_CONFIRM[1]) < 60):  # 且 y 与实测外层确认接近（防误匹配）
            print(f"[分解] 外层提示弹窗已出现（确认 {cs:.3f} @{cc}），点击确认…")  # 打印日志
            adb_tap(DECOMPOSE_OUTER_CONFIRM[0], DECOMPOSE_OUTER_CONFIRM[1])  # 点实测外层确认坐标
            time.sleep(1.5)     # 等 1.5s
            break               # 跳出循环
        gs, gc = detect_button(frame, TEMPLATE_DECOMPOSE_GO, roi=decompose_go_roi(frame))  # 检测金黄「分解」
        if gs is not None and gs >= DECOMPOSE_TH and gc:  # 匹配达标
            print(f"[分解] 点击弹框内「分解」（{gs:.3f} @{gc}），1s 后检查提示…")  # 打印日志
            adb_tap(gc[0], gc[1])  # 点击金黄分解按钮
            time.sleep(1.0)     # 等 1s
            continue            # 继续循环
        print(f"[分解] 未检测到金黄「分解」按钮（第 {i+1} 轮）…")  # 打印重试日志
        time.sleep(1)           # 等 1s 再试
    # 4) 高价值二次确认（不一定出现）→ 点内层确认
    for i in range(4):          # 最多 4 轮
        frame = capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        vs, vc = detect_button(frame, TEMPLATE_DECOMPOSE_HIGHVALUE, roi=decompose_popup_roi(frame))  # 中央检测高价值弹窗
        if vs is not None and vs >= DECOMPOSE_TH and vc:  # 匹配达标
            print(f"[分解] 高价值二次确认出现（{vs:.3f}），点击内层确认…")  # 打印日志
            adb_tap(DECOMPOSE_INNER_CONFIRM[0], DECOMPOSE_INNER_CONFIRM[1])  # 点内层确认坐标
            time.sleep(2.0)     # 等 2s
            break               # 跳出循环
        rs, rc = detect_button(frame, TEMPLATE_DECOMPOSE_RESULT, roi=decompose_popup_roi(frame))  # 检测「获得道具」弹窗
        if rs is not None and rs >= DECOMPOSE_TH and rc:  # 已出现获得道具 → 无高价值确认
            print(f"[分解] 未出现高价值确认，直接到获得道具弹窗（{rs:.3f}）")  # 打印日志
            break               # 跳出循环
        time.sleep(1)           # 等 1s 再试
    # 5) 获得道具弹窗 → 点确认
    for i in range(6):          # 最多 6 轮
        frame = capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        rs, rc = detect_button(frame, TEMPLATE_DECOMPOSE_RESULT, roi=decompose_popup_roi(frame))  # 检测「获得道具」弹窗
        if rs is not None and rs >= DECOMPOSE_TH and rc:  # 匹配达标
            print(f"[分解] 「获得道具」弹窗出现（{rs:.3f}），点击确认…")  # 打印日志
            adb_tap(DECOMPOSE_RESULT_CONFIRM[0], DECOMPOSE_RESULT_CONFIRM[1])  # 点获得道具确认坐标
            time.sleep(2.0)     # 等 2s
            break               # 跳出循环
        time.sleep(1)           # 等 1s 再试
    # 6) 点 × 关闭分解弹框 → 点返回箭头回主页面（确保回城镇）
    for i in range(4):          # 最多 4 轮
        frame = capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        ts, _ = detect_button(frame, TEMPLATE_DECOMPOSE_TITLE, roi=decompose_title_roi(frame))  # 检测分解标题栏
        if ts is None or ts < DECOMPOSE_TH:  # 标题栏已消失 → 弹框已关闭
            print("[分解] 分解弹框已关闭")  # 打印日志
            break               # 跳出循环
        adb_tap(DECOMPOSE_CLOSE_X[0], DECOMPOSE_CLOSE_X[1])  # 点右上角 × 关闭
        time.sleep(1.5)         # 等 1.5s
    print("[分解] 返回主页面…")  # 打印返回日志
    for i in range(4):          # 最多 4 轮
        frame = capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        if at_town(frame):      # 已在城镇主界面
            print("[分解] 已回到城镇主界面")  # 打印日志
            break               # 跳出循环
        # 背包界面左上角返回箭头（实测 (50,43) 有效）；BACK 备用
        adb_tap(50, 43)         # 点背包界面左上角返回箭头
        time.sleep(2.0)         # 等 2s
        frame2 = capture_hdmi()  # 再截一张
        if frame2 is not None and at_town(frame2):  # 已回城镇
            print("[分解] 已回到城镇主界面")  # 打印日志
            break               # 跳出循环
        adb_back()              # 兜底：按返回键
        time.sleep(2.0)         # 等 2s
    print("[分解] 分解装备流程完成")  # 打印完成日志
    return True                 # 返回完成


# ---------------- 刷新神秘商店 ----------------
def shop_icon_roi(frame):
    """神秘商店图标搜索区域：城镇顶部入口"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    return (int(w * 0.55), 0, int(w * 0.85), int(h * 0.18))  # 顶部 55%-85% 宽


def shop_back_roi(frame):
    """商店「返回」按钮搜索区域：画面左上角（真实按钮位置）"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    return (0, 0, int(w * 0.30), int(h * 0.25))  # 左上 30% 宽 × 25% 高


def refresh_roi(frame):
    """刷新按钮搜索区域：画面底部（真实按钮位置 y 85%-100%）"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    return (int(w * 0.35), int(h * 0.85), int(w * 0.75), h)  # 底部 35%-75% 宽 × 85%-100% 高


def shop_refresh():
    """刷新神秘商店（邮件领取后调用）：
    等 SHOP_WAIT_AFTER_HOME 秒 → 检测商店「返回」按钮（已打开标志）：
      有 → 商店已打开；无 → 检测「神秘商店」图标（城镇顶部）→ 点击 → 2s 再检（最多10轮）
    购买流程（最多 SHOP_ROUNDS 轮）：
      检测「购买」→ 有 → 点击 → 2s → 检测「购买物品」弹框 → 有 → 再点「购买」→ 2s
      → 检测「刷新」按钮（付费图标「1000 立即刷新」）→ 检测到则【不点击】→ 点「返回」回主页面
      无「购买」→ 检测「刷新」→ 检测到同样不点 → 点「返回」回主页面
    返回 True（流程完成）或 False（未打开商店）。"""
    print(f"[商店] 等待 {SHOP_WAIT_AFTER_HOME:.0f}s（回主页缓冲）…")  # 打印等待日志
    time.sleep(SHOP_WAIT_AFTER_HOME)  # 等 2s（回主页后界面缓冲）
    # 1) 打开神秘商店
    opened = False              # 商店是否已打开
    for i in range(10):         # 最多 10 轮
        frame = capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        h, w = frame.shape[0], frame.shape[1]  # 画面高宽
        bs, bc = detect_button(frame, TEMPLATE_SHOP_BACK, roi=shop_back_roi(frame))  # 检测商店「返回」按钮（已打开标志）
        if bs is not None and bs >= SHOP_BACK_TH and bc:  # 匹配达标 → 商店已打开
            print(f"[商店] 检测到「返回按钮」（相似度 {bs:.3f}），商店已打开 ✓")  # 打印日志
            opened = True       # 标记已打开
            break               # 跳出循环
        ss, sc = detect_button(frame, TEMPLATE_SHOP, roi=shop_icon_roi(frame))  # 检测「神秘商店」图标（城镇顶部）
        if ss is not None and ss >= SHOP_TH and sc:  # 匹配达标
            print(f"[商店] 点击「神秘商店」图标（相似度 {ss:.3f}，坐标 {sc}），2s 后检查…")  # 打印日志
            adb_tap(sc[0], sc[1])  # 点击神秘商店图标
            time.sleep(2.0)     # 等 2s 让商店打开
            continue            # 继续循环
        print(f"[商店] 未检测到神秘商店图标（第 {i+1} 轮），2s 后重试…")  # 打印重试日志
        time.sleep(2)           # 等 2s 再试
    if not opened:              # 10 轮没打开商店
        print("[商店] 多次尝试未打开神秘商店")  # 打印失败日志
        return False            # 返回失败

    # 2) 购买流程（检测到付费「刷新」图标即停止并返回主页面）
    for r in range(SHOP_ROUNDS):  # 最多 SHOP_ROUNDS=10 轮
        frame = capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        # a. 检测「购买」按钮
        bs, bc = detect_button(frame, TEMPLATE_BUY)  # 全图检测「购买」
        if bs is not None and bs >= BUY_TH and bc:  # 匹配达标
            print(f"[商店] 点击「购买」（相似度 {bs:.3f}，坐标 {bc}），3s 后查弹框…")  # 打印日志
            adb_tap(bc[0], bc[1])  # 点击购买按钮
            time.sleep(3.0)     # 等 3s 让购买弹框出现（用户要求 3s）
            frame2 = capture_hdmi()  # 再截一张
            if frame2 is not None:  # 截图成功
                ps, pc = detect_button(frame2, TEMPLATE_BUY_POPUP)  # 检测「购买物品」弹框
                if ps is not None and ps >= POPUP_TH and pc:  # 弹框已出现
                    # 检测弹框内「购买」按钮：最多重复检查 3 次 × 2s，仍失败 → 提示音并退出程序
                    buy_popup_found = False  # 弹框内购买是否已点击
                    for k in range(3):      # 重复检查 3 次
                        bs2, bc2 = detect_button(frame2, TEMPLATE_BUY_POPUP_BTN)  # 检测弹框内「购买」（红底白字模板）
                        if bs2 is not None and bs2 >= BUY_TH and bc2:  # 匹配达标
                            print(f"[商店] 「购买物品」弹框出现（{ps:.3f}），点击弹框内「购买」（{bs2:.3f} @{bc2}）")  # 打印日志
                            adb_tap(bc2[0], bc2[1])  # 点击弹框内购买按钮
                            time.sleep(2.0)  # 等 2s 让购买完成
                            buy_popup_found = True  # 标记点击成功
                            break               # 跳出重查循环
                        print(f"[商店] 弹框内「购买」未识别（第 {k+1} 次/共3次），2s 后重查…")  # 打印重查日志
                        time.sleep(2)           # 等 2s 再查
                        frame2 = capture_hdmi()  # 重新截取画面
                        if frame2 is None:      # 截图失败
                            break               # 跳出（截图失败不再重试）
                    if not buy_popup_found:     # 3 次检查都未识别到弹框内「购买」
                        print("[商店] 弹框内「购买」按钮 3 次检查均失败，提示音并退出程序")  # 打印失败日志
                        beep(True); time.sleep(0.4); beep(True); time.sleep(0.4); beep(True)  # 三响提示音提醒
                        sys.exit(1)             # 退出程序（用户要求：识别失败直接退出）
                    # 购买成功 → 关闭「完成购买」奖励弹窗
                    frame3 = capture_hdmi()  # 再截一张
                    if frame3 is not None:  # 截图成功
                        ds, dc = detect_button(frame3, TEMPLATE_BUY_DONE)  # 检测「完成购买」奖励弹窗
                        if ds is not None and ds >= BUY_DONE_TH and dc:  # 弹窗出现
                            ks, kc = detect_button(frame3, TEMPLATE_BUY_DONE_CONFIRM)  # 检测奖励弹窗「确认」
                            if ks is not None and ks >= BUY_DONE_CONFIRM_TH and kc:  # 匹配达标
                                print(f"[商店] 「完成购买」奖励弹窗出现（{ds:.3f}），点击「确认」（{ks:.3f} @{kc}）")  # 打印日志
                                adb_tap(kc[0], kc[1])  # 点击确认关闭弹窗
                                time.sleep(2.0)  # 等 2s
                            else:  # 弹窗内没有确认按钮
                                print("[商店] 奖励弹窗内未检测到「确认」按钮")  # 打印日志
                        else:  # 奖励弹窗未出现
                            print(f"[商店] 未出现「完成购买」奖励弹窗（{ds or 0:.3f}）")  # 打印日志
                else:  # 购买弹框未出现
                    print(f"[商店] 未出现「购买物品」弹框（{ps or 0:.3f}）")  # 打印日志
            time.sleep(1.0)     # 等 1s
            # b. 检测「免费刷新」→ 点击（免费次数可用时继续刷新购买）；检测「付费刷新」→ 不点 → 返回主页面
            frame4 = capture_hdmi()  # 再截一张
            if frame4 is not None:  # 截图成功
                fs, fc = detect_button(frame4, TEMPLATE_REFRESH_FREE, roi=refresh_roi(frame4))  # 底部检测「免费刷新」
                if fs is not None and fs >= REFRESH_FREE_TH and fc:  # 匹配达标 → 免费刷新可点
                    print(f"[商店] 检测到「免费刷新」按钮（{fs:.3f} @{fc}），点击刷新…")  # 打印日志
                    adb_tap(fc[0], fc[1])  # 点击免费刷新
                    time.sleep(2.0)  # 等 2s 让商店刷新
                    continue    # 继续循环（重新检测购买）
                rs, rc = detect_button(frame4, TEMPLATE_REFRESH, roi=refresh_roi(frame4))  # 底部检测「付费刷新」
                if rs is not None and rs >= REFRESH_TH and rc:  # 匹配达标 → 付费刷新不点
                    print(f"[商店] 检测到「付费刷新」按钮（{rs:.3f}），【不点击】，返回主页面…")  # 打印日志
                    return _leave_shop(frame4)  # 返回主页面并结束
                print(f"[商店] 未检测到刷新按钮（免费 {fs or 0:.3f} / 付费 {rs or 0:.3f}），2s 后重试…")  # 打印重试日志
                time.sleep(2)   # 等 2s 再试
                continue        # 继续循环
            time.sleep(2)       # 截图失败 → 等 2s
            continue            # 继续循环
        # b. 无购买按钮 → 检测「免费刷新」→ 点击；检测「付费刷新」→ 不点 → 返回主页面
        fs, fc = detect_button(frame, TEMPLATE_REFRESH_FREE, roi=refresh_roi(frame))  # 底部检测「免费刷新」
        if fs is not None and fs >= REFRESH_FREE_TH and fc:  # 匹配达标 → 免费刷新可点
            print(f"[商店] 无购买按钮，检测到「免费刷新」（{fs:.3f} @{fc}），点击刷新…")  # 打印日志
            adb_tap(fc[0], fc[1])  # 点击免费刷新
            time.sleep(2.0)     # 等 2s 让商店刷新
            continue            # 继续循环（重新检测购买）
        rs, rc = detect_button(frame, TEMPLATE_REFRESH, roi=refresh_roi(frame))  # 底部检测「付费刷新」
        if rs is not None and rs >= REFRESH_TH and rc:  # 匹配达标 → 付费刷新不点
            print(f"[商店] 无购买按钮，检测到「付费刷新」（{rs:.3f}），【不点击】，返回主页面…")  # 打印日志
            return _leave_shop(frame)  # 返回主页面并结束
        print(f"[商店] 未检测到「购买」/「刷新」（第 {r+1} 轮），2s 后重试…")  # 打印重试日志
        if r >= SHOP_ROUNDS - 1:  # 已到最后一轮
            # 最后一轮仍未找到 → 点「返回」回主页面，避免商店界面残留
            return _leave_shop(frame)  # 返回主页面并结束
        time.sleep(2)           # 等 2s 再试
    print("[商店] 购买流程循环结束")  # 打印结束日志
    return True                 # 返回完成


def _leave_shop(frame):
    """点击商店左上角「返回」按钮回到主页面，返回 True"""
    h, w = frame.shape[0], frame.shape[1]  # 画面高宽
    bs, bc = detect_button(frame, TEMPLATE_SHOP_BACK, roi=shop_back_roi(frame))  # 左上角检测「返回」按钮
    if bs is not None and bs >= SHOP_BACK_TH and bc:  # 匹配达标
        print(f"[商店] 点击「返回」按钮（相似度 {bs:.3f}，坐标 {bc}），回到主页面 ✓")  # 打印日志
        adb_tap(bc[0], bc[1])  # 点击返回按钮
        time.sleep(2.0)         # 等 2s 回到主页面
        return True             # 返回完成
    print("[商店] 未检测到「返回」按钮，尝试直接结束")  # 没找到返回按钮
    return True                 # 仍按完成处理（避免卡死）


# ---------------- 辅助：模板 ----------------
def make_template():
    """截取当前 HDMI 画面保存到 templates/，供用户裁剪出按钮"""
    os.makedirs(IMG_DIR, exist_ok=True)  # 确保模板目录存在
    frame = capture_hdmi()      # 截取当前游戏画面
    if frame is None:           # 截图失败
        print("截图失败，请确认模拟器已启动、ADB 已连接")  # 打印提示
        return False            # 返回失败
    cv2.imwrite(RAW_PATH, frame)  # 保存原始画面到 templates/challenge_raw.png
    print(f"已保存当前游戏画面：{RAW_PATH}")  # 打印保存路径
    print("请用画图裁剪出「再次挑战」按钮区域，另存为 templates/template_challenge.png。")  # 提示下一步
    return True                 # 返回成功


# ---------------- 自测 ----------------
def selftest():
    """合成一张含按钮的画面，验证 detect_challenge 逻辑"""
    os.makedirs(IMG_DIR, exist_ok=True)  # 确保模板目录存在
    print("自测：合成模拟结算画面…")  # 打印开始日志
    frame = np.full((1207, 2142, 3), (30, 30, 45), dtype=np.uint8)  # 深色底（模拟游戏画面尺寸）
    # 画一个橙色按钮 + 文字（用英文替代，仅验证匹配流程）
    bx1, by1, bx2, by2 = 900, 600, 1242, 700  # 按钮区域坐标（左上/右下）
    cv2.rectangle(frame, (bx1, by1), (bx2, by2), (30, 130, 255), -1)  # 画橙色矩形按钮
    cv2.putText(frame, "CHALLENGE", (930, 665), cv2.FONT_HERSHEY_SIMPLEX, 1.2,  # 按钮上写字
                (255, 255, 255), 3, cv2.LINE_AA)  # 白色文字
    # 模板 = 同一按钮区域（同源 → 相似度应接近 1.0）
    tmp_path = os.path.join(tempfile.gettempdir(), "_selftest_tmpl.png")  # 临时模板路径
    cv2.imwrite(tmp_path, frame[by1:by2, bx1:bx2])  # 把按钮区域保存为模板
    global TEMPLATE_PATH        # 声明修改全局模板路径
    TEMPLATE_PATH = tmp_path    # 临时替换为合成模板
    score, center = detect_challenge(frame)  # 用合成画面做匹配
    print(f"检测结果：相似度 {score:.3f}，中心 {center}")  # 打印检测结果
    ok = score is not None and score >= MATCH_TH  # 是否达标
    print("自测", "通过 ✓" if ok else "失败 ✗")  # 打印判定结果
    return 0 if ok else 1       # 返回码：0 通过 / 1 失败


# ---------------- 移动自测 ----------------
def test_move():
    """按住 → 3 秒，验证提权后 PostMessage 方向键是否能让角色前进"""
    hwnd = find_game_window()   # 查找游戏窗口
    if hwnd is None:            # 没找到窗口
        msgbox(f"未找到标题包含「{TITLE_KEY}」的游戏窗口，请先启动游戏。", "dnfm-auto 挂机")  # 弹窗提示
        return 1                # 返回失败
    print(f"已找到游戏窗口 hwnd={hwnd}")  # 打印窗口句柄
    force_foreground(hwnd)      # 前置游戏窗口
    time.sleep(0.5)             # 等 0.5s 让置前生效
    print("测试：按住 → 3 秒（请观察游戏角色是否前进）…")  # 提示观察
    hold_key(hwnd, VK["right"], 3.0)  # 按住 → 3 秒
    print("已松开 →。若角色移动了，说明按键通道正常，可以正式挂机。")  # 提示结果
    beep(True)                  # 播放成功提示音
    return 0                    # 返回成功


# ---------------- 主流程 ----------------
def retemplate_from_live():
    """从当前实况画面按千分比裁剪「再次挑战」「领奖结算」按钮作新模板。
    用于窗口/HDMI 分辨率变化导致模板失配时一键重制（运行前请把游戏画面停在结算界面）。
    返回 0=成功 1=失败"""
    frame = capture_hdmi()       # 截取当前实况画面
    if frame is None:            # 截图失败
        print("[模板] 截图失败，无法重裁模板")
        return 1                 # 返回失败
    h, w = frame.shape[0], frame.shape[1]  # 画面尺寸
    # 按千分比裁剪两个按钮（位置固定，与分辨率无关）：
    c1 = frame[int(h * 0.105):int(h * 0.175), int(w * 0.83):int(w * 0.94)]   # 「再次挑战」
    c2 = frame[int(h * 0.195):int(h * 0.265), int(w * 0.83):int(w * 0.94)]   # 「领奖结算」
    if c1.size == 0 or c2.size == 0:   # 裁剪区域无效
        print("[模板] 裁剪区域无效")
        return 1                 # 返回失败
    cv2.imwrite(TEMPLATE_PATH, c1)     # 覆盖「再次挑战」模板
    cv2.imwrite(TEMPLATE_REWARD, c2)   # 覆盖「领奖结算」模板
    save_window_size(w, h)       # 同步更新 config 里的窗口尺寸记录
    s1, _ = detect_challenge(frame)    # 立即验证再次挑战
    s2, _ = detect_reward(frame)       # 立即验证领奖结算
    ok = s1 is not None and s1 >= MATCH_TH  # 再次挑战达标即视为成功
    print(f"[模板] 重裁完成：再次挑战 {s1:.3f}、领奖结算 {s2 if s2 is None else round(s2,3)}（画面 {w}x{h}）")
    return 0 if ok else 1        # 返回成功/失败


def main():
    # 纯工具模式不涉及按键操作 → 无需提权，先处理（提权会重启进程导致输出丢失）
    if "--retemplate" in sys.argv:  # 重裁模板模式（窗口尺寸变化后，画面停在结算界面时运行）
        sys.exit(retemplate_from_live())  # 从当前画面重裁两个模板并返回结果
    if "--capture" in sys.argv:  # 截图模式参数
        sys.exit(0 if make_template() else 1)  # 截图并返回结果

    ensure_admin()  # 游戏以管理员运行，必须先提权，否则按键被 UIPI 拦截

    if "--selftest" in sys.argv:  # 自测模式参数
        sys.exit(selftest())    # 跑自测并以结果作为退出码
    if "--testmove" in sys.argv:  # 移动测试模式参数
        sys.exit(test_move())   # 跑移动测试

    if not os.path.exists(TEMPLATE_PATH):  # 「再次挑战」模板不存在
        print(f"缺少模板：{TEMPLATE_PATH}")  # 打印提示
        make_template()         # 自动截一张图方便制作模板
        msgbox("请将截图中「再次挑战」按钮区域裁剪保存为 templates/template_challenge.png，再重新运行。",
               "dnfm-auto 挂机")  # 弹窗说明制作方法
        return                  # 退出

    print("=" * 50)             # 打印开始分隔线
    ensure_window_size()        # 校验窗口尺寸：与上次记录不一致则自动调整（模板匹配依赖画面分辨率）
    print("  DNF 起源 自动过图挂机")  # 打印程序标题
    print(f"  模板：{TEMPLATE_PATH}")  # 打印模板路径
    print("  运行中…（Ctrl+C 停止）")  # 打印运行提示
    print("=" * 50)             # 打印结尾分隔线
    beep(True)                  # 启动提示音

    try:                        # 尝试查找游戏窗口
        hwnd = find_game_window()  # 按标题找窗口
    except RuntimeError as e:   # 非 Windows 环境
        msgbox(str(e), "dnfm-auto 挂机")  # 弹窗报错
        return                  # 退出
    if hwnd is None:            # 没找到窗口
        msgbox(f"未找到标题包含「{TITLE_KEY}」的游戏窗口，请先启动游戏。", "dnfm-auto 挂机")  # 弹窗提示
        return                  # 退出
    print(f"已找到游戏窗口 hwnd={hwnd}")  # 打印窗口句柄
    force_foreground(hwnd)   # 前置窗口，确保按键送达
    time.sleep(0.5)             # 等 0.5s 让置前生效

    rounds = 0                  # 挂机轮数计数
    try:                        # 捕获手动停止/运行时错误
        while True:             # 无限挂机循环（直到领奖完成或手动停止）
            rounds += 1         # 轮数自增
            print(f"\n===== 第 {rounds} 轮 =====")  # 打印轮次标题
            force_foreground(hwnd)   # 每轮开始前置一次（跑图期间可能被其他窗口抢占）
            stage1_forward(hwnd)  # 阶段1：跑图前进
            result = stage2_wait_challenge(hwnd)  # 阶段2：检测「再次挑战」/「领奖结算」
            if result == "challenge":  # 检测到再次挑战
                stage3_trigger_challenge(hwnd)   # 点击「再次挑战」（阶段3）
            elif result == "restart":  # 超时未检测到按钮（3 分钟）
                print(f"\n[重启] 长时间未检测到「再次挑战」/「领奖结算」，从本轮跑图重新开始…")  # 打印重启日志
                continue               # 跳过下方领奖逻辑，回到循环开头重新跑图（stage1）
            else:               # 检测到领奖结算
                done = stage3_reward_settle(hwnd)   # 点击「领奖结算」→「结算」→「确认」（领奖流程）
                if done == "done":  # 领奖完成
                    # mail_claim()  # 已注释：邮件领取（用户要求只保留跑图）
                    print("\n[完成] 领奖确认完成，脚本自动退出（已注释邮件/商店/切角，只保留跑图）。")  # 打印完成日志
                    beep(True)  # 播放成功提示音
                    return 0    # 直接退出脚本（不弹窗阻塞，自动退出）
    except KeyboardInterrupt:   # 用户按 Ctrl+C
        print("\n已手动停止（Ctrl+C）")  # 打印停止日志
        beep(True)              # 播放提示音
        msgbox(f"挂机已手动停止，共完成 {rounds} 轮。", "dnfm-auto 挂机")  # 弹窗告知轮数
    except RuntimeError as e:   # 运行时错误（ADB 断开等）
        print(f"\n异常停止：{e}")  # 打印异常
        beep(False)             # 播放失败提示音
        msgbox(str(e), "dnfm-auto 挂机")  # 弹窗显示错误


if __name__ == "__main__":      # 仅当本文件被直接运行时（而非被 import）才执行
    main()                      # 进入主流程
