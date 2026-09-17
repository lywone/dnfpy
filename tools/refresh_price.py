# -*- coding: utf-8 -*-
"""独立功能：刷新商品价格（神秘商店刷新按钮自动点击）
====================================================
流程：
  循环检测「刷新」按钮（黑底金色图标 40x33，商店界面底部）：
    有 → 点击刷新 → 等 2.5s → 继续检测
    无 → 等 0.5s → 再检测
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

TEMPLATE_REFRESH_PRICE = os.path.join(a.IMG_DIR, "template_refresh_price.png")  # 「刷新」按钮模板路径（循环箭头图标 42x37，实况重裁居中）
REFRESH_TH = 0.60   # 刷新按钮匹配阈值（同源模板实测 1.0）
WAIT_AFTER_CLICK = 2.5  # 点击刷新后等待秒数（等刷新完成、价格变化）
WAIT_NO_BUTTON = 0.5    # 未检测到刷新按钮时的轮询间隔秒数


def main():
    """主流程：无限循环检测刷新按钮 → 有则点击，无则轮询"""
    print("=== 刷新商品价格（独立功能）===")  # 打印程序标题
    print("检测到「刷新」按钮 → 点击，2.5s 后继续；未检测到 → 0.5s 检测一次")  # 打印使用说明
    print("按 Ctrl+C 停止。")  # 打印停止方式提示
    n = 0  # 刷新点击次数计数
    while True:  # 无限循环直到用户 Ctrl+C
        frame = a.capture_hdmi()  # 截取当前游戏画面
        if frame is None:       # 截图失败（模拟器/ADB 异常）
            print("[刷新] 截图失败，1s 后重试…")  # 打印失败日志
            time.sleep(1)       # 等 1s 再试
            continue            # 继续循环
        # 检测「刷新」按钮：刷新图标位于拍卖行弹窗中部（「可以交易」下方），直接全图检测
        rs, rc = a.detect_button(frame, TEMPLATE_REFRESH_PRICE)
        if rs is not None and rs >= REFRESH_TH and rc:  # 找到刷新按钮且匹配达标
            n += 1  # 点击次数 +1
            print(f"[刷新] 第 {n} 次点击「刷新」（相似度 {rs:.3f} @{rc}），2.5s 后继续检测…")  # 打印点击日志
            a.adb_tap(rc[0], rc[1])  # 点击刷新按钮（adb 底层点击）
            time.sleep(WAIT_AFTER_CLICK)  # 等 2.5s 让刷新完成
        else:  # 未找到刷新按钮
            print(f"[刷新] 未检测到「刷新」按钮（相似度 {rs or 0:.3f}），0.5s 后再检测…")  # 打印轮询日志
            time.sleep(WAIT_NO_BUTTON)  # 等 0.5s 再检测


if __name__ == "__main__":  # 仅当本文件被直接运行时才执行
    try:                    # 捕获用户中断
        main()              # 调用主流程
    except KeyboardInterrupt:  # 用户按 Ctrl+C
        print("\n[停止] 用户手动停止刷新脚本。")  # 打印停止日志
        sys.exit(0)         # 正常退出（返回码 0）
