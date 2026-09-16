# -*- coding: utf-8 -*-
"""单独测试：切换角色功能（合并进 mail_claim 前先跑通）
流程：
  等 2s（回主页缓冲）→ 点「选角」→「挑战进度」面板出现
  → 滚到最上面（5s）→ 慢慢往下滚 → 检测「可刷新」→ 点击
  → 检测「开始游戏」变黄 → 点击 → 5s 后提示退出
  未变黄 → 2s 后再点「可刷新」（最多 8 轮）
用法：python tools\test_char_switch.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auto_run as a

TITLE = "dnfm-auto 切换角色测试"


def main():
    print("=" * 52)
    print("  单独测试：切换角色功能")
    print("  流程：点选角 → 面板 → 滚到顶 → 找可刷新 → 点开始游戏")
    print("  请确认游戏已切到城镇主界面。")
    print("=" * 52)
    a.beep(True)
    try:
        ok = a.char_switch()
    except RuntimeError as e:
        print(f"\n异常：{e}")
        a.beep(False)
        return 1
    if ok:
        print("\n[完成] 切换角色流程执行完毕。")
        a.msgbox("切换角色流程执行完毕。", TITLE)
        return 0
    print("\n[失败] 切换角色未完成，请检查游戏画面后重试。")
    a.beep(False)
    return 1


if __name__ == "__main__":
    sys.exit(main())
