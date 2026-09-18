# -*- coding: utf-8 -*-
"""独立功能：刷新商品价格（拍卖行购买弹窗刷新按钮自动点击）
====================================================
背景结论（实测）：
  1. 刷新按钮真实位置 = 弹窗行情信息区右侧 (854,349)（用户手动点击确认有效）。
  2. 按钮有两个状态：
     - 可刷新态：黑底金色 Q（循环箭头）图标 33x39（用户从 (854,349) 截图提供）→ 可点击
     - 刷新后/冷却态：图标变样（33x39 模板匹配仅 0.258）→ 不可点
  3. 旧模板 42x37 过泛，全画面匹配 113 个位置（含 (703,291) 相似图标）→ 点错目标。
  4. adb tap 对模拟器 display 2 已失效 → 点击改用真实鼠标点击（mouse_click，需管理员）。

流程：
  限定 ROI（仅 (854,349) 附近）检测「可刷新态」图标 33x39：
    有 → 点击 (854,349) → 等 2.5s（刷新 3→2→1 倒数+完成）→ 继续检测
    无 → 等 0.5s → 再检测（等冷却结束回到可刷新态）
  重复以上步骤，直到用户按 Ctrl+C 手动停止。

用法：
  python tools\\refresh_price.py
"""
import os       # 操作系统路径处理：拼模板路径
import sys      # 系统路径：sys.path 注入工程根目录（才能 import auto_run）
import time     # 时间控制：点击后的等待与未找到时的轮询间隔

# 把工程根目录加入模块搜索路径（本文件在 tools\ 下，上一级即工程根）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auto_run as a  # 引入 auto_run.py 的函数（截图/模板匹配/点击等）

TEMPLATE_REFRESH_PRICE = os.path.join(a.IMG_DIR, "template_refresh_price.png")  # 「刷新」按钮模板路径（可刷新态图标 33x39，黑底金色 Q，用户从 (854,349) 截图提供）
REFRESH_TH = 0.60    # 刷新按钮匹配阈值（同源模板实测 0.955）
WAIT_AFTER_CLICK = 2.5  # 点击刷新后等待秒数（等 3→2→1 倒数与刷新完成）
WAIT_NO_BUTTON = 0.5    # 未检测到可刷新态按钮时的轮询间隔秒数
REFRESH_POS = (854, 349)  # 刷新按钮固定坐标（HDMI 坐标，用户手动点击确认有效）
# 限定搜索区域：仅 (854,349) 附近（排除画面中其他相似循环箭头图标，如 (703,291)）
REFRESH_ROI = (790, 290, 920, 410)  # (x1, y1, x2, y2)：刷新按钮周边矩形


def detect_refresh_button(frame):
    """在限定 ROI 内检测可刷新态刷新按钮，返回 (相似度, 中心坐标)；未找到返回 (None, None)"""
    x1, y1, x2, y2 = REFRESH_ROI                     # 展开 ROI 边界
    h, w = frame.shape[:2]                           # 画面尺寸
    x1 = max(0, min(x1, w - 1))                      # 边界保护（左）
    y1 = max(0, min(y1, h - 1))                      # 边界保护（上）
    x2 = max(0, min(x2, w - 1))                      # 边界保护（右）
    y2 = max(0, min(y2, h - 1))                      # 边界保护（下）
    roi = frame[y1:y2, x1:x2]                        # 裁剪 ROI 区域
    rs, rc = a.detect_button(roi, TEMPLATE_REFRESH_PRICE)  # ROI 内检测模板
    if rc:                                           # 有匹配
        cx = x1 + rc[0]                              # ROI 内中心 → 全图 x
        cy = y1 + rc[1]                              # ROI 内中心 → 全图 y
        return rs, (cx, cy)                          # 返回全图坐标
    return None, None                                # 未找到


def main():
    """主流程：无限循环在限定区域检测可刷新态刷新按钮 → 有则点击，无则轮询等冷却"""
    a.ensure_admin()  # 必须提权：鼠标点击模拟器窗口（管理员 Qt）需管理员权限（UIPI），非管理员自动弹 UAC 提权重启
    print("=== 刷新商品价格（独立功能）===")  # 打印程序标题
    print(f"检测「可刷新态」刷新按钮（限定 ({REFRESH_ROI})）→ 点击 ({REFRESH_POS[0]},{REFRESH_POS[1]})；未检测到 → 0.5s 轮询等冷却")  # 打印使用说明
    print("按 Ctrl+C 停止。")  # 打印停止方式提示
    n = 0  # 刷新点击次数计数
    while True:  # 无限循环直到用户 Ctrl+C
        frame = a.capture_hdmi()  # 截取当前游戏画面
        if frame is None:       # 截图失败（模拟器/ADB 异常）
            print("[刷新] 截图失败，1s 后重试…")  # 打印失败日志
            time.sleep(1)       # 等 1s 再试
            continue            # 继续循环
        rs, rc = detect_refresh_button(frame)  # ROI 内检测可刷新态刷新按钮
        if rs is not None and rs >= REFRESH_TH and rc:  # 找到可刷新态按钮且匹配达标
            n += 1  # 点击次数 +1
            print(f"[刷新] 第 {n} 次点击「刷新」（相似度 {rs:.3f} @{rc} → 固定点 {REFRESH_POS}），2.5s 后继续检测…")  # 打印点击日志
            a.mouse_click(*REFRESH_POS)  # 点击刷新按钮固定坐标（真实鼠标点击：adb tap 对 display2 已失效）
            time.sleep(WAIT_AFTER_CLICK)  # 等 2.5s 让 3→2→1 倒数与刷新完成
        else:  # 未检测到可刷新态按钮（冷却中/界面不在弹窗）
            print(f"[刷新] 未检测到「可刷新态」按钮（相似度 {rs or 0:.3f}），0.5s 后再检测…")  # 打印轮询日志
            time.sleep(WAIT_NO_BUTTON)  # 等 0.5s 再检测


if __name__ == "__main__":  # 仅当本文件被直接运行时才执行
    try:                    # 捕获用户中断
        main()              # 调用主流程
    except KeyboardInterrupt:  # 用户按 Ctrl+C
        print("\n[停止] 用户手动停止刷新脚本。")  # 打印停止日志
        sys.exit(0)         # 正常退出（返回码 0）
