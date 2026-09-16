# -*- coding: utf-8 -*-
"""
独立功能：循环（接收邮件 + 刷新神秘商店 + 切换角色），可单跑任意子功能
====================================================
《地下城与勇士：起源》—— 循环执行：
  每轮：邮件领取 → 刷新神秘商店 → 切换角色
  （分解装备流程已注释暂不启用）
  切换角色成功后 → 自动开始下一轮（再次邮件 → 商店 → 切换角色）
  没有可切换的角色（全部角色无可刷新）→ 结束循环退出

用法：
  python mail_claim.py          循环三连（默认）：邮件 → 商店 → 切角 → 重复
  python mail_claim.py mail     只跑邮件领取
  python mail_claim.py shop     只跑刷新神秘商店（含邮件）
  python mail_claim.py char     只跑切换角色（单次）
  python mail_claim.py --quiet  静默模式（不弹窗）
"""
import os   # 操作系统路径处理：用于拼脚本目录、定位 auto_run.py
import sys  # 系统参数/路径：sys.argv 读命令行参数、sys.path 注入脚本目录
import time  # 时间控制：流程中各类延时（等待界面切换、缓冲等）

# 把本脚本所在目录加入模块搜索路径，才能 import 同目录下的 auto_run.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auto_run as a   # 引入 auto_run.py 的所有函数（截图/模板匹配/点击/邮箱/商店/切角等）

TITLE = "dnfm-auto 独立功能"   # 弹窗标题：msgbox 提示框的统一标题


def run_loop(quiet):
    """循环三连：接收邮件 → 刷新神秘商店 → 切换角色。
    （分解装备流程已注释，后续需要可取消注释启用）
    切角成功 → 下一轮；切角无可刷新（False）→ 结束循环。"""
    rounds = 0   # 循环轮数计数（从 0 开始，每轮 +1）
    while True:  # 无限循环：切角失败（无可刷新）时才 break 退出
        rounds += 1  # 进入新的一轮，轮数自增
        print("\n" + "=" * 52)   # 打印轮次分隔线（空行 + 52 个等号）
        print(f"  第 {rounds} 轮：接收邮件 → 刷新商店 → 切换角色")   # 打印本轮标题
        print("=" * 52)   # 打印分隔线（52 个等号）
        a.beep(True)  # 播放成功提示音（每轮开始提醒一次）
        # 0) 确保在城镇主界面（不在则返回）
        for i in range(4):  # 最多尝试 4 次回城（模拟器界面可能有层级，需多次 BACK）
            frame = a.capture_hdmi()  # 截取当前游戏画面（BGR ndarray 或 None）
            if frame is not None and a.at_town(frame):  # 画面有效且判断在城镇 → 直接跳出循环
                break  # 已在城镇，无需回城，进入正式流程
            print(f"[第{rounds}轮] 不在城镇主界面，返回城镇（第 {i+1} 次）…")  # 打印回城日志
            a.adb_back()  # 模拟按 Android 返回键（keyevent 4）返回上一层
            time.sleep(2.0)  # 等待 2s 让界面切换完成后再截图检查
        # 1) 接收邮件
        ok = a.mail_claim()  # 调用 auto_run 的邮箱领取流程（点邮箱→领取全部→确认→返回）
        if not ok:  # 邮件领取返回 False（多次尝试未完成）
            print(f"[第{rounds}轮] 邮件领取未完成，继续尝试商店与切角…")  # 打印提示并继续后续步骤
        # 2) 分解装备（暂不需要，已注释）
        # print(f"\n[第{rounds}轮] 邮件领取完成，开始分解装备…")
        # a.decompose_equip()
        # 3) 刷新神秘商店
        print(f"\n[第{rounds}轮] 邮件领取完成，开始刷新神秘商店…")  # 打印商店流程开始日志
        a.shop_refresh()  # 调用 auto_run 的商店刷新购买流程
        # 4) 切换角色（成功 → 下一轮；无可刷新 → 结束循环）
        print(f"\n[第{rounds}轮] 神秘商店刷新完成，开始切换角色…")  # 打印切角流程开始日志
        ok = a.char_switch()  # 调用 auto_run 的切换角色流程（找可刷新→开始游戏→确认）
        if not ok:  # 切角返回 False：无可刷新角色 / 面板未打开
            print(f"\n[第{rounds}轮] 没有可切换的角色（无可刷新），结束循环。")  # 打印结束日志
            a.beep(False)  # 播放失败提示音（低频）提醒用户循环已结束
            if not quiet:  # 非静默模式才弹窗（--quiet 参数时跳过）
                a.msgbox("所有角色均无可刷新，切换角色循环结束。", TITLE)  # 弹窗告知用户
            return 0  # 正常退出（返回码 0），结束整个循环程序
        print(f"\n[第{rounds}轮] 切换角色成功，5s 后开始下一轮…")  # 打印等待下一轮日志
        time.sleep(5.0)  # 等待 5s（让游戏进入新角色场景）后再开始下一轮


def main():
    args = [x for x in sys.argv[1:] if x != "--quiet"]  # 过滤掉 --quiet 后的模式参数列表
    quiet = "--quiet" in sys.argv  # 是否静默模式（True=不弹窗）
    mode = args[0] if args else "loop"  # 第一个参数为模式名；无参数时默认 loop
    print("=" * 52)  # 打印开头分隔线
    print("  DNF 起源 独立功能")  # 打印程序标题
    if mode == "char":  # 模式：只跑切换角色
        print("  模式：切换角色（选角 → 面板 → 找可刷新 → 开始游戏）")  # 打印该模式说明
    elif mode == "mail":  # 模式：只跑邮件领取
        print("  模式：邮件领取")  # 打印该模式说明
    elif mode == "shop":  # 模式：邮件 + 刷新商店
        print("  模式：刷新神秘商店")  # 打印该模式说明
    elif mode == "loop":  # 模式：循环三连（默认）
        print("  模式：循环三连（邮件 → 商店 → 切角 → 重复）")  # 打印该模式说明
    else:  # 未知模式参数
        print(f"  未知模式：{mode}（支持 mail / shop / char / loop）")  # 提示合法模式
        return 2  # 返回码 2 表示参数错误退出
    print("  请确认游戏已切到城镇主界面。")  # 提醒用户先把游戏切到城镇
    print("=" * 52)  # 打印结尾分隔线
    a.beep(True)  # 启动提示音（告知脚本开始执行）
    try:  # 捕获运行期异常（模拟器断开/模板缺失等）
        if mode == "loop":  # 循环三连模式
            return run_loop(quiet)  # 进入无限循环，直到无可刷新角色后返回
        if mode == "char":  # 单次切角模式
            ok = a.char_switch()  # 调用切角流程（找可刷新→开始游戏→确认）
            if ok:  # 切角成功
                a.beep(True)  # 播放成功提示音
                print("\n[完成] 切换角色流程执行完毕。")  # 打印完成日志
                if not quiet:  # 非静默模式
                    a.msgbox("切换角色流程执行完毕。", TITLE)  # 弹窗告知完成
                return 0  # 返回码 0 正常退出
            a.beep(False)  # 切角失败：播放失败提示音
            print("\n[失败] 切换角色未完成（无可刷新角色），请检查游戏画面后重试。")  # 打印失败原因
            return 1  # 返回码 1 表示流程未完成退出
        ok = a.mail_claim()  # mail/shop 模式共同前置步骤：先领取邮件
        if not ok:  # 邮件领取失败
            a.beep(False)  # 播放失败提示音
            print("\n[失败] 邮件领取未完成。")  # 打印失败日志
            return 1  # 返回码 1 退出
        if mode == "mail":  # 纯邮件模式：领取完成即结束
            print("\n[邮件] 邮件领取完成。")  # 打印完成日志
            if not quiet:  # 非静默模式
                a.msgbox("邮件领取完成。", TITLE)  # 弹窗告知完成
            return 0  # 返回码 0 正常退出
        # shop 单次（邮件领取后继续刷新商店）
        print("\n[邮件] 邮件领取完成，开始刷新神秘商店…")  # 打印进入商店流程日志
        a.shop_refresh()  # 调用商店刷新购买流程
        print("\n[商店] 神秘商店刷新完成。")  # 打印商店完成日志
        a.beep(True)  # 播放成功提示音
        if not quiet:  # 非静默模式
            a.msgbox("神秘商店刷新完成。", TITLE)  # 弹窗告知完成
        return 0  # 返回码 0 正常退出
    except RuntimeError as e:  # 捕获 RuntimeError（如 ADB 断开、非 Windows 环境）
        print(f"\n异常：{e}")  # 打印异常信息
        a.beep(False)  # 播放失败提示音
        if not quiet:  # 非静默模式
            a.msgbox(f"异常：{e}", TITLE)  # 弹窗显示异常内容
        return 1  # 返回码 1 表示异常退出


if __name__ == "__main__":  # 仅当本文件被直接运行时（而非被 import）才执行
    sys.exit(main())  # 调用主函数并用其返回值作为进程退出码
