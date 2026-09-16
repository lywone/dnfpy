# -*- coding: utf-8 -*-
"""
测试点击「邮箱」图标（HDMI 版）
==============================
关键结论（模拟器重启后验证）：
  - 游戏窗口客户区只显示低分辨率 UI（右下角功能栏被裁掉，邮箱图标不可见）
  - HDMI 屏（display 3，2142x1207 横屏）显示完整 UI，邮箱图标在右下角
  - 用 `adb screencap -d 3` 截图可直接获得完整游戏画面（= input 坐标系）
  - 模板匹配 test_icon.png → 邮箱中心坐标 = adb tap 的 input 坐标

流程：
  1. adb screencap -d 3 截取 HDMI 完整游戏画面
  2. 多尺度模板匹配 test_icon.png 定位邮箱图标
  3. 直接 adb tap（HDMI 坐标 = input 坐标）
  4. 点击完成给出提示（提示音 + 弹窗）；未找到也提示

用法：
    python test_click_mail.py
"""
import os
import glob
import time
import subprocess
import winsound
import pymsgbox

import cv2
import numpy as np

# ---------------- 配置 ----------------
ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images", "xuanjuese.png")
MATCH_MIN = 0.60                    # 匹配相似度阈值（0.929 实测，0.6 足够安全）
ADB_HOST = "127.0.0.1:5555"        # 应用宝模拟器 adb 地址
DISPLAY_ID = "3"                    # 游戏所在 display（HDMI 屏）
TMP_REMOTE = "/sdcard/jueseyemian.png"  # 设备端临时截图路径
TMP_LOCAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images", "jueseyemian.png")


# ---------------- 提示音 ----------------
def beep(freq: int = 880, dur: int = 250):
    try:
        winsound.Beep(freq, dur)
    except Exception:
        pass


def notify(title, msg, ok=True):
    """成功/失败提示：提示音 + 弹窗"""
    beep(1175, 250) if ok else beep(200, 500)
    try:
        pymsgbox.alert(msg, title)
    except Exception as e:
        print(f"弹窗失败：{e}")


# ---------------- adb 工具 ----------------
def find_adb():
    """在应用宝安装目录里找 adb.exe（自动适配版本目录）"""
    candidates = (glob.glob(r"C:\Program Files\Tencent\Androws\Application\*\adb.exe") +
                  glob.glob(r"C:\Program Files\Tencent\AndrowsData\Component\Androws\adb.exe"))
    return candidates[0] if candidates else "adb"


def adb_shell(*args):
    subprocess.run([find_adb(), "-s", ADB_HOST, "shell", *args],
                   capture_output=True, timeout=60)


def capture_hdmi():
    """adb screencap -d 3 截取 HDMI 完整游戏画面，返回 numpy BGR 数组"""
    adb_shell("screencap", "-d", DISPLAY_ID, "-p", TMP_REMOTE)
    subprocess.run([find_adb(), "-s", ADB_HOST, "pull", TMP_REMOTE, TMP_LOCAL],
                   capture_output=True, timeout=60)
    img = cv2.imread(TMP_LOCAL)
    if img is None:
        return None
    return img


def adb_tap(ix, iy):
    """adb 触摸点击（display 3，HDMI 逻辑坐标）"""
    subprocess.run([find_adb(), "-s", ADB_HOST, "shell", "input", "-d", DISPLAY_ID,
                    "tap", str(int(ix)), str(int(iy))],
                   capture_output=True, timeout=30)


# ---------------- 图标定位 ----------------
def find_mail_icon(frame_np):
    """多尺度模板匹配，返回 (相似度, 图标中心坐标) 或 (None, None)"""
    tmpl = cv2.imread(ICON_PATH)
    if tmpl is None:
        return None, None
    best_val, best_loc, best_scale = 0.0, None, None
    for scale in [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6,
                  0.7, 0.8, 0.9, 1.0, 1.2, 1.5, 2.0]:
        tw = max(8, int(tmpl.shape[1] * scale))
        th = max(8, int(tmpl.shape[0] * scale))
        resized = cv2.resize(tmpl, (tw, th))
        result = cv2.matchTemplate(frame_np, resized, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val > best_val:
            best_val, best_loc, best_scale = max_val, max_loc, scale
    if best_loc is None:
        return None, None
    cx = best_loc[0] + int(tmpl.shape[1] * best_scale) // 2
    cy = best_loc[1] + int(tmpl.shape[0] * best_scale) // 2
    return float(best_val), (cx, cy)


# ---------------- 主流程 ----------------
def main():
    print("正在截取 HDMI 游戏画面（display 3）…")
    frame = capture_hdmi()
    if frame is None:
        print("截图失败，请确认：模拟器已启动、adb 已连接（127.0.0.1:5555）")
        notify("dnfm-auto 邮箱点击",
               "获取游戏画面失败。\n请确认模拟器已启动、ADB 已连接。", ok=False)
        return

    h, w = frame.shape[:2]
    print(f"游戏画面尺寸：{w}x{h}")

    score, center = find_mail_icon(frame)
    if center is None or score < MATCH_MIN:
        print(f"未找到邮箱图标（最佳相似度 {score if score else 0:.3f}，阈值 {MATCH_MIN}）")
        print("请确认游戏处于主城界面（右下角显示 邮箱/社交/角色/打造/冒险/背包 图标栏）。")
        notify("dnfm-auto 邮箱点击",
               "未找到邮箱图标。\n请确认游戏处于主城界面（右下角有邮箱图标）后再运行。", ok=False)
        return

    cx, cy = center
    print(f"找到邮箱图标：相似度 {score:.3f}，坐标 ({cx}, {cy})")

    # ---- 点击（带重试与验证）----
    clicked = False
    for attempt in range(1, 4):
        print(f"正在点击（第 {attempt} 次）…")
        time.sleep(0.5)
        adb_tap(cx, cy)
        time.sleep(1.2)
        # 验证：重新截图，若右下角邮箱图标消失（相似度下降）说明已进入邮箱界面
        frame = capture_hdmi()
        if frame is None:
            continue
        s2, _ = find_mail_icon(frame)
        if s2 is None or s2 < MATCH_MIN:
            clicked = True
            print("已进入邮箱界面")
            break
        print(f"界面未变化（邮箱图标相似度 {s2:.3f}），重试…")

    if clicked:
        print("点击完成")
        notify("dnfm-auto 邮箱点击",
               f"邮箱图标点击完成，已打开邮箱界面。\n位置：({cx}, {cy})", ok=True)
    else:
        print("点击失败：多次尝试后界面未变化")
        notify("dnfm-auto 邮箱点击",
               "邮箱点击失败：多次尝试后界面未变化。", ok=False)


if __name__ == "__main__":
    main()
