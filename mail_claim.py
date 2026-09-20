# -*- coding: utf-8 -*-
"""
独立功能：循环（接收邮件 + 刷新神秘商店 + 切换角色），可单跑任意子功能
====================================================
《地下城与勇士：起源》—— 循环执行：
  每轮：邮件领取 → 分解装备 → 刷新神秘商店 → 切换角色
  切换角色成功后 → 自动开始下一轮（再次邮件 → 分解装备 → 商店 → 切换角色）
  没有可切换的角色（全部角色无可刷新）→ 结束循环退出

用法：
  python mail_claim.py          循环（默认）：邮件 → 分解装备 → 商店 → 切角 → 重复
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

# 「提示」对话框标题栏模板（templates/template_decompose_hint.png，点金黄分解后弹出）
DECOMPOSE_HINT_TPL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "template_decompose_hint.png")


def _decompose_back_to_town():
    """从分解/背包界面返回城镇主界面（点左上角返回箭头 + BACK 兜底）。"""
    print("[分解] 返回主页面…")
    for i in range(4):          # 最多 4 轮
        frame = a.capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        if a.at_town(frame):    # 已在城镇主界面
            print("[分解] 已回到城镇主界面")  # 打印日志
            return              # 返回
        a.adb_tap(50, 43)       # 点背包界面左上角返回箭头（实测有效）
        time.sleep(2.0)         # 等 2s
        frame2 = a.capture_hdmi()  # 再截一张
        if frame2 is not None and a.at_town(frame2):  # 已回城镇
            print("[分解] 已回到城镇主界面")  # 打印日志
            return              # 返回
        a.adb_back()            # 兜底：按返回键
        time.sleep(2.0)         # 等 2s


def _decompose_equip():
    """分解装备流程（仅在 mail_claim.py 内实现，不改 auto_run.py）：
    前置：等 DECOMPOSE_WAIT_AFTER_MAIL → 点背包 → 点分解按钮 → 等分解弹框
    1) 点弹框内金黄「分解」→ 等 2s → 检查外层确认按钮（5 次 × 2s）→ 点外层确认
       ；5 次未出 → 打印文字提示，继续走关闭分解流程
    2) 点外层确认 → 等 2s → 检查高价值二次确认（5 次 × 2s）→ 点内层确认
       ；期间先出「获得道具」弹窗则视为无高价值确认，直接进结果环节
       ；5 次未出 → 打印文字提示，继续走关闭分解流程
    3) 点内层确认 → 等 2s → 检查「获得道具」弹窗（5 次 × 2s）→ 点结果确认
       ；5 次未出 → 打印文字提示
    4) 点 × 关闭分解弹框 → _decompose_back_to_town() 回主页面，往下一流程
    任一步失败都不中断，统一走关闭/回主页面。"""
    print(f"[分解] 等待 {a.DECOMPOSE_WAIT_AFTER_MAIL:.0f}s（邮件完成缓冲）…")  # 打印等待日志
    time.sleep(a.DECOMPOSE_WAIT_AFTER_MAIL)  # 等 2s（邮件流程结束后缓冲）

    # 前置1：点「背包」图标 → 检测「分解」按钮（背包界面标志）
    opened = False              # 背包界面是否已打开
    for i in range(a.DECOMPOSE_MAX_TRY):  # 最多 10 轮
        frame = a.capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        h, w = frame.shape[0], frame.shape[1]  # 画面高宽
        ds, dc = a.detect_button(frame, a.TEMPLATE_DECOMPOSE_BTN, roi=a.decompose_btn_roi(frame))  # 检测「分解」按钮
        if ds is not None and ds >= a.DECOMPOSE_TH and dc:  # 匹配达标 → 已在背包界面
            print(f"[分解] 背包界面已打开（检测到「分解」按钮 {ds:.3f}）")  # 打印日志
            opened = True       # 标记已打开
            break               # 跳出循环
        bs, bc = a.detect_button(frame, a.TEMPLATE_BAG, roi=(0, int(h * 0.6), w, h))  # 底部检测「背包」图标
        if bs is not None and bs >= a.DECOMPOSE_TH and bc:  # 匹配达标
            print(f"[分解] 点击「背包」图标（{bs:.3f}），1s 后检查…")  # 打印日志
            a.adb_tap(bc[0], bc[1])  # 点击背包图标（打开背包）
            time.sleep(1.0)     # 等 1s
            continue            # 继续循环
        print(f"[分解] 未检测到「背包」图标（第 {i+1} 轮），1s 后重试…")  # 打印重试日志
        time.sleep(1)           # 等 1s 再试
    if not opened:              # 10 轮没打开背包
        print("[分解] 未能打开背包界面，跳过分解，继续下一流程")  # 打印失败日志
        return False            # 返回失败

    # 前置2：点「分解」按钮 → 检测分解弹框（分解标题栏，顶部中央 ROI）
    popup_opened = False        # 分解弹框是否已打开
    clicked_btn = False         # 是否已点过「分解」入口按钮（点过就不再重复点，防误点已弹出的框）
    for i in range(a.DECOMPOSE_MAX_TRY):  # 最多 10 轮
        frame = a.capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        ts, tc = a.detect_button(frame, a.TEMPLATE_DECOMPOSE_TITLE, roi=a.decompose_title_roi(frame))  # 顶部检测分解标题栏
        if ts is not None and ts >= a.DECOMPOSE_TH and tc:  # 匹配达标 → 弹框已出现
            print(f"[分解] 分解弹框已出现（标题栏 {ts:.3f}）")  # 打印日志
            popup_opened = True  # 标记已打开
            break               # 跳出循环
        print(f"[分解] 第 {i+1} 轮 TITLE 分数={ts if ts is not None else 'None'}（阈值 {a.DECOMPOSE_TH}）")  # 调试：打印分数
        if clicked_btn:         # 已经点过分解入口按钮 → 不再重复点，只等弹框出现
            time.sleep(1.5)     # 等 1.5s 再查
            continue            # 继续等
        ds, dc = a.detect_button(frame, a.TEMPLATE_DECOMPOSE_BTN, roi=a.decompose_btn_roi(frame))  # 检测「分解」按钮
        if ds is not None and ds >= a.DECOMPOSE_TH and dc:  # 匹配达标
            print(f"[分解] 点击「分解」按钮（{ds:.3f}），2s 后检查弹框…")  # 打印日志
            a.adb_tap(dc[0], dc[1])  # 点击分解按钮（打开分解弹框）
            clicked_btn = True  # 标记已点过，后续不再重复点
            time.sleep(2.0)     # 等 2s 让弹框完全加载
            continue            # 继续循环
        print(f"[分解] 未检测到「分解」按钮（第 {i+1} 轮）…")  # 打印重试日志
        time.sleep(1)           # 等 1s 再试
    if not popup_opened:        # 没打开分解弹框
        print("[分解] 未能打开分解弹框，直接返回主页面")  # 打印日志
        _decompose_back_to_town()  # 返回主页面
        return False            # 返回失败

    # 1) 点弹框内金黄「分解」→ 等 2s → 检查外层确认按钮（5 次 × 2s）
    for i in range(a.DECOMPOSE_MAX_TRY):  # 最多 10 轮点金黄分解
        frame = a.capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        gs, gc = a.detect_button(frame, a.TEMPLATE_DECOMPOSE_GO, roi=a.decompose_go_roi(frame))  # 检测金黄「分解」
        if gs is not None and gs >= a.DECOMPOSE_TH and gc:  # 匹配达标
            print(f"[分解] 点击弹框内「分解」（{gs:.3f}），2s 后检查外层确认…")  # 打印日志
            a.adb_tap(gc[0], gc[1])  # 点击金黄分解按钮
            break               # 已点中，进入等待确认阶段
        print(f"[分解] 未检测到金黄「分解」按钮（第 {i+1} 轮）…")  # 打印重试日志
        time.sleep(1)           # 等 1s 再试
    # 等待 2s → 检查「提示」对话框（hint 标题栏模板），5 次 × 2s
    time.sleep(2.0)             # 点完分解先等 2s 让弹窗弹出
    outer_ok = False            # 外层确认是否点到
    for i in range(5):          # 最多检查 5 次
        frame = a.capture_hdmi()  # 截取当前画面
        if frame is not None:   # 画面有效
            hs, hc = a.detect_button(frame, DECOMPOSE_HINT_TPL, roi=a.decompose_popup_roi(frame))  # 中央检测「提示」标题栏
            if hs is not None and hs >= a.DECOMPOSE_TH and hc:  # 「提示」对话框出现
                print(f"[分解] 「提示」对话框出现（标题栏 {hs:.3f}），点击确认…")  # 打印日志
                # 优先在对话框内实时检测确认按钮位置；检测不到则用实测坐标兜底
                cs, cc = a.detect_button(frame, a.TEMPLATE_DECOMPOSE_CONFIRM, roi=a.decompose_popup_roi(frame))  # 检测确认按钮
                if cs is not None and cs >= a.DECOMPOSE_TH and cc:  # 实时检测到确认按钮
                    a.adb_tap(cc[0], cc[1])  # 点实时检测到的确认按钮
                else:           # 检测不到 → 用实测坐标兜底
                    a.adb_tap(a.DECOMPOSE_OUTER_CONFIRM[0], a.DECOMPOSE_OUTER_CONFIRM[1])  # 点实测外层确认坐标
                outer_ok = True  # 标记已点外层确认
                break           # 跳出检查循环
        print(f"[分解] 第 {i+1}/5 次未检测到「提示」对话框，2s 后再查…")  # 打印等待日志
        time.sleep(2.0)         # 等 2s 再查
    if not outer_ok:            # 5 次都没等到「提示」对话框
        print("[分解] 5 次检查均未出现「提示」对话框，关闭分解流程，继续返回主页面…")  # 文字提示

    # 2) 点外层确认后 → 等 2s → 检查高价值二次确认（5 次 × 2s）
    highvalue_ok = False        # 高价值确认是否点到（True=有点到；False=未点到/未出现）
    if outer_ok:                # 仅当外层确认点到才继续
        time.sleep(2.0)         # 点完外层确认先等 2s
        for i in range(5):      # 最多检查 5 次
            frame = a.capture_hdmi()  # 截取当前画面
            if frame is not None:  # 画面有效
                vs, vc = a.detect_button(frame, a.TEMPLATE_DECOMPOSE_HIGHVALUE, roi=a.decompose_popup_roi(frame))  # 中央检测高价值弹窗
                if vs is not None and vs >= a.DECOMPOSE_TH and vc:  # 高价值二次确认出现
                    print(f"[分解] 高价值二次确认出现（{vs:.3f}），点击内层确认…")  # 打印日志
                    a.adb_tap(a.DECOMPOSE_INNER_CONFIRM[0], a.DECOMPOSE_INNER_CONFIRM[1])  # 点内层确认坐标
                    highvalue_ok = True  # 标记已点内层确认
                    break       # 跳出检查循环
                rs, rc = a.detect_button(frame, a.TEMPLATE_DECOMPOSE_RESULT, roi=a.decompose_popup_roi(frame))  # 同时检测「获得道具」弹窗
                if rs is not None and rs >= a.DECOMPOSE_TH and rc:  # 已出结果 → 说明无高价值确认
                    print(f"[分解] 未出现高价值确认，直接到获得道具弹窗（{rs:.3f}），进入结果环节")  # 打印日志
                    highvalue_ok = True  # 视为继续走结果环节（无高价值弹窗是正常情况）
                    break       # 跳出检查循环
            print(f"[分解] 第 {i+1}/5 次未检测到高价值确认，2s 后再查…")  # 打印等待日志
            time.sleep(2.0)     # 等 2s 再查
        if not highvalue_ok:    # 5 次都没等到
            print("[分解] 5 次检查均未出现高价值确认弹窗，关闭分解流程，继续返回主页面…")  # 文字提示

    # 3) 点内层确认后 → 等 2s → 检查「获得道具」弹窗（5 次 × 2s）
    result_ok = False           # 结果弹窗是否点到
    if highvalue_ok:            # 仅当上一环节通过才继续
        time.sleep(2.0)         # 点完内层确认先等 2s
        for i in range(5):      # 最多检查 5 次
            frame = a.capture_hdmi()  # 截取当前画面
            if frame is not None:  # 画面有效
                rs, rc = a.detect_button(frame, a.TEMPLATE_DECOMPOSE_RESULT, roi=a.decompose_popup_roi(frame))  # 检测「获得道具」弹窗
                if rs is not None and rs >= a.DECOMPOSE_TH and rc:  # 匹配达标
                    print(f"[分解] 「获得道具」弹窗出现（{rs:.3f}），点击确认…")  # 打印日志
                    a.adb_tap(a.DECOMPOSE_RESULT_CONFIRM[0], a.DECOMPOSE_RESULT_CONFIRM[1])  # 点获得道具确认坐标
                    result_ok = True  # 标记已点结果确认
                    break       # 跳出检查循环
            print(f"[分解] 第 {i+1}/5 次未检测到「获得道具」弹窗，2s 后再查…")  # 打印等待日志
            time.sleep(2.0)     # 等 2s 再查
        if not result_ok:       # 5 次都没等到
            print("[分解] 5 次检查均未出现「获得道具」弹窗，关闭分解流程，继续返回主页面…")  # 文字提示

    # 4) 点 × 关闭分解弹框 → 返回主页面
    for i in range(4):          # 最多 4 轮
        frame = a.capture_hdmi()  # 截取当前画面
        if frame is None:       # 截图失败
            time.sleep(1)       # 等 1s
            continue            # 继续循环
        ts, _ = a.detect_button(frame, a.TEMPLATE_DECOMPOSE_TITLE, roi=a.decompose_title_roi(frame))  # 检测分解标题栏
        if ts is None or ts < a.DECOMPOSE_TH:  # 标题栏已消失 → 弹框已关闭
            print("[分解] 分解弹框已关闭")  # 打印日志
            break               # 跳出循环
        a.adb_tap(a.DECOMPOSE_CLOSE_X[0], a.DECOMPOSE_CLOSE_X[1])  # 点右上角 × 关闭
        time.sleep(1.5)         # 等 1.5s
    _decompose_back_to_town()   # 返回主页面（城镇）
    print("[分解] 分解装备流程完成")  # 打印完成日志
    return True                 # 返回完成


def run_loop(quiet):
    """循环：接收邮件 → 分解装备 → 刷新神秘商店 → 切换角色。
    切角成功 → 下一轮；切角无可刷新（False）→ 结束循环。"""
    rounds = 0   # 循环轮数计数（从 0 开始，每轮 +1）
    while True:  # 无限循环：切角失败（无可刷新）时才 break 退出
        rounds += 1  # 进入新的一轮，轮数自增
        print("\n" + "=" * 52)   # 打印轮次分隔线（空行 + 52 个等号）
        print(f"  第 {rounds} 轮：接收邮件 → 分解装备 → 刷新商店 → 切换角色")   # 打印本轮标题
        print("=" * 52)   # 打印分隔线（52 个等号）
        # 注：切换角色成功后进入下一轮【不播放提示音】（用户要求：避免每轮都响），退出脚本时才响
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
            print(f"[第{rounds}轮] 邮件领取未完成，继续尝试分解装备、商店与切角…")  # 打印提示并继续后续步骤
        # 2) 分解装备（本脚本内实现，不改 auto_run.py）
        print(f"\n[第{rounds}轮] 邮件领取完成，开始分解装备…")
        _decompose_equip()
        # 3) 刷新神秘商店
        print(f"\n[第{rounds}轮] 邮件领取完成，开始刷新神秘商店…")  # 打印商店流程开始日志
        a.shop_refresh()  # 调用 auto_run 的商店刷新购买流程
        # 4) 切换角色（成功 → 下一轮；无可刷新 → 结束循环）
        print(f"\n[第{rounds}轮] 神秘商店刷新完成，开始切换角色…")  # 打印切角流程开始日志
        ok = a.char_switch()  # 调用 auto_run 的切换角色流程（找可刷新→开始游戏→确认）
        if not ok:  # 切角返回 False：无可刷新角色 / 面板未打开
            print(f"\n[第{rounds}轮] 没有可切换的角色（无可刷新），结束循环。")  # 打印结束日志
            a.beep(True)  # 播放成功提示音（用户要求：退出脚本之后再给提示音，正常完成）
            if not quiet:  # 非静默模式才弹窗（--quiet 参数时跳过）
                a.msgbox("所有角色均无可刷新，切换角色循环结束。", TITLE)  # 弹窗告知用户
            return 0  # 正常退出（返回码 0），结束整个循环程序
        print(f"\n[第{rounds}轮] 切换角色成功，等待 8s 后按 ESC 关闭提示弹框…")  # 打印等待下一轮日志
        time.sleep(8.0)  # 先等 8s（让新角色场景加载完成、提示弹框出现）再按 ESC
        a.press_esc()   # 按 ESC 键：把新角色进入城镇后的提示弹框去掉（引导/活动等）
        time.sleep(1.0)  # 等 1s（ESC 生效 + 界面稳定）后再往下执行下一轮


def main():
    a.ensure_admin()  # 游戏窗口是管理员 Qt 窗口：必须提权才能用 keybd_event 注入键盘（ESC 关弹窗），非管理员时自动弹 UAC 提权重启
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
    elif mode == "loop":  # 模式：循环（默认）
        print("  模式：循环（邮件 → 分解装备 → 商店 → 切角 → 重复）")  # 打印该模式说明
    else:  # 未知模式参数
        print(f"  未知模式：{mode}（支持 mail / shop / char / loop）")  # 提示合法模式
        return 2  # 返回码 2 表示参数错误退出
    print("  请确认游戏已切到城镇主界面。")  # 提醒用户先把游戏切到城镇
    print("=" * 52)  # 打印结尾分隔线
    a.beep(True)  # 启动提示音（告知脚本开始执行）
    try:  # 捕获运行期异常（模拟器断开/模板缺失等）
        if mode == "loop":  # 循环模式
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
