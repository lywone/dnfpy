# -*- coding: utf-8 -*-
"""单独测试：刷新神秘商店功能（合并进 mail_claim 前先跑通）
流程：
  等 2s（回主页缓冲）→ 检测「返回按钮」（商店界面标志）：
    有 → 商店已打开 → 进入刷新购买流程
    无 → 检测「神秘商店」图标（城镇顶部）→ 点击 → 2s → 再检测（循环，最多 10 轮）
  刷新购买流程（最多 10 轮）：
    a. 检测「购买」按钮 → 有 → 点击 → 2s → 检测「购买物品」弹框 → 有 → 再点「购买」→ 2s
    b. 检测「刷新」按钮 → 点击 → 2s
    c. 回到 a 重复
用法：python tools\test_shop_refresh.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auto_run as a

TEMPLATE_SHOP = os.path.join(a.IMG_DIR, "template_shop.png")
TEMPLATE_SHOP_BACK = os.path.join(a.IMG_DIR, "template_shop_back.png")
TEMPLATE_BUY = os.path.join(a.IMG_DIR, "template_buy.png")
TEMPLATE_BUY_POPUP = os.path.join(a.IMG_DIR, "template_buy_popup.png")
TEMPLATE_REFRESH = os.path.join(a.IMG_DIR, "template_refresh.png")

SHOP_TH = 0.60        # 神秘商店图标阈值（新同源模板 1.0）
BACK_TH = 0.60        # 商店返回按钮阈值（城镇左上角误匹配 0.586）
BUY_TH = 0.60         # 购买按钮阈值
POPUP_TH = 0.60       # 购买物品弹框阈值
REFRESH_TH = 0.60     # 刷新按钮阈值
WAIT_AFTER_HOME = 2.0   # 回主页后等待秒数


def shop_icon_roi(frame):
    """神秘商店图标搜索区域：城镇顶部入口（x 55%-85%, y 0-18%）"""
    h, w = frame.shape[0], frame.shape[1]
    return (int(w * 0.55), 0, int(w * 0.85), int(h * 0.18))


def back_roi(frame):
    """商店返回按钮搜索区域：画面左上角（真实按钮位置）"""
    h, w = frame.shape[0], frame.shape[1]
    return (0, 0, int(w * 0.30), int(h * 0.25))


def main():
    print("=== 刷新神秘商店 单独测试 ===")
    print(f"等待 {WAIT_AFTER_HOME:.0f}s（回主页缓冲）…")
    time.sleep(WAIT_AFTER_HOME)

    # 1) 打开神秘商店
    opened = False
    for i in range(10):
        frame = a.capture_hdmi()
        if frame is None:
            time.sleep(1)
            continue
        h, w = frame.shape[0], frame.shape[1]
        bs, bc = a.detect_button(frame, TEMPLATE_SHOP_BACK, roi=back_roi(frame))
        if bs is not None and bs >= BACK_TH and bc:
            print(f"[商店] 检测到「返回按钮」（相似度 {bs:.3f}），商店已打开 ✓")
            opened = True
            break
        ss, sc = a.detect_button(frame, TEMPLATE_SHOP, roi=shop_icon_roi(frame))
        if ss is not None and ss >= SHOP_TH and sc:
            print(f"[商店] 点击「神秘商店」图标（相似度 {ss:.3f}，坐标 {sc}），2s 后检查…")
            a.adb_tap(sc[0], sc[1])
            time.sleep(2.0)
            continue
        print(f"[商店] 未检测到神秘商店图标（第 {i+1} 轮），2s 后重试…")
        time.sleep(2)

    if not opened:
        print("[商店] 多次尝试未打开神秘商店")
        a.beep(False)
        return 1

    # 2) 刷新购买循环
    for r in range(10):
        frame = a.capture_hdmi()
        if frame is None:
            time.sleep(1)
            continue
        # a. 检测「购买」按钮
        bs, bc = a.detect_button(frame, TEMPLATE_BUY)
        if bs is not None and bs >= BUY_TH and bc:
            print(f"[购买] 点击「购买」（相似度 {bs:.3f}，坐标 {bc}），2s 后查弹框…")
            a.adb_tap(bc[0], bc[1])
            time.sleep(2.0)
            # 检测「购买物品」弹框
            frame2 = a.capture_hdmi()
            if frame2 is not None:
                ps, pc = a.detect_button(frame2, TEMPLATE_BUY_POPUP)
                if ps is not None and ps >= POPUP_TH and pc:
                    print(f"[购买] 出现「购买物品」弹框（相似度 {ps:.3f}），再点「购买」…")
                    bs2, bc2 = a.detect_button(frame2, TEMPLATE_BUY)
                    if bs2 is not None and bs2 >= BUY_TH and bc2:
                        a.adb_tap(bc2[0], bc2[1])
                        print(f"[购买] 弹框内点击「购买」（相似度 {bs2:.3f}，坐标 {bc2}）")
                        time.sleep(2.0)
                    else:
                        print("[购买] 弹框内未检测到「购买」按钮")
                else:
                    print(f"[购买] 未出现「购买物品」弹框（{ps or 0:.3f}）")
            # b. 检测「刷新」按钮 → 点击
            time.sleep(1.0)
            frame3 = a.capture_hdmi()
            if frame3 is not None:
                rs, rc = a.detect_button(frame3, TEMPLATE_REFRESH)
                if rs is not None and rs >= REFRESH_TH and rc:
                    print(f"[刷新] 点击「刷新」（相似度 {rs:.3f}，坐标 {rc}），2s 后查购买…")
                    a.adb_tap(rc[0], rc[1])
                    time.sleep(2.0)
                    continue
                print(f"[刷新] 未检测到「刷新」按钮（{rs or 0:.3f}），2s 后重试…")
                time.sleep(2)
                continue
            time.sleep(2)
            continue
        # 没有购买按钮 → 检测刷新按钮
        rs, rc = a.detect_button(frame, TEMPLATE_REFRESH)
        if rs is not None and rs >= REFRESH_TH and rc:
            print(f"[刷新] 无购买按钮，点击「刷新」（相似度 {rs:.3f}，坐标 {rc}），2s 后查购买…")
            a.adb_tap(rc[0], rc[1])
            time.sleep(2.0)
            continue
        print(f"[刷新] 未检测到「购买」/「刷新」（第 {r+1} 轮），2s 后重试…")
        time.sleep(2)

    print("[商店] 刷新购买循环结束")
    a.beep(False)
    return 1


if __name__ == "__main__":
    sys.exit(main())
