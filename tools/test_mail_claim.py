# -*- coding: utf-8 -*-
"""单独测试：邮箱领取功能（v2 含确认+返回邮箱）
流程：
  等 5s（返回城镇缓冲）→ 检测「领取全部物品」：
    有 → 点击 → 3s → 步骤A
    无 → 检测「邮箱」图标 → 点击 → 2s → 再检测（循环，最多 10 轮）
  步骤A：检测「确认」（橙黄渐变）→ 点击 → 2s（最多 3 轮，无则跳过）
  步骤B：检测「返回邮箱」→ 有点击 → 2s 复查；无（已回主页面）→ 完成退出
用法：python tools\test_mail_claim.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auto_run as a

TEMPLATE_MAIL = os.path.join(a.IMG_DIR, "template_mail.png")
TEMPLATE_CLAIM = os.path.join(a.IMG_DIR, "template_claim.png")
TEMPLATE_MAIL_CONFIRM = os.path.join(a.IMG_DIR, "template_mail_confirm.png")
TEMPLATE_MAIL_BACK = os.path.join(a.IMG_DIR, "template_mail_back.png")
MAIL_TH = 0.60          # 邮箱图标阈值
CLAIM_TH = 0.65         # 领取全部阈值（同源模板 1.0，城镇底部误匹配 0.586）
MAIL_CONFIRM_TH = 0.60  # 邮箱确认按钮阈值
MAIL_BACK_TH = 0.60     # 返回邮箱按钮阈值（新同源模板：邮箱界面 1.0，城镇误匹配 0.377）
WAIT_AFTER_TOWN = 5.0   # 返回城镇后等待秒数


def mail_roi(frame):
    """邮箱图标搜索区域：画面底部（按钮栏），排除场景建筑误匹配"""
    h, w = frame.shape[0], frame.shape[1]
    return (0, int(h * 0.82), w, h)


def claim_roi(frame):
    """领取全部按钮搜索区域：画面底部（邮箱界面按钮行）"""
    h, w = frame.shape[0], frame.shape[1]
    return (0, int(h * 0.85), w, h)


def mail_back_roi(frame):
    """返回邮箱按钮搜索区域：画面左上角（真实按钮在此），
    排除城镇右上角「频道」文字误匹配（实测 0.615）"""
    h, w = frame.shape[0], frame.shape[1]
    return (0, 0, int(w * 0.30), int(h * 0.25))


def main():
    print("=== 邮箱领取 v2 单独测试（含确认+返回邮箱） ===")
    print(f"等待 {WAIT_AFTER_TOWN:.0f}s（返回城镇缓冲）…")
    time.sleep(WAIT_AFTER_TOWN)

    claimed = False
    for i in range(10):
        frame = a.capture_hdmi()
        if frame is None:
            print(f"[{i+1}] 截图失败，1s 后重试…")
            time.sleep(1)
            continue
        # 1) 检测「领取全部物品」→ 有则点击
        cs, cc = a.detect_button(frame, TEMPLATE_CLAIM, roi=claim_roi(frame))
        if cs is not None and cs >= CLAIM_TH and cc:
            print(f"[领取] 点击「领取全部物品」（相似度 {cs:.3f}，坐标 {cc}），3s 后查「确认」…")
            a.adb_tap(cc[0], cc[1])
            time.sleep(3.0)
            claimed = True
            break
        # 2) 没有「领取全部」→ 检测「邮箱」图标（底部区域）→ 点击
        ms, mc = a.detect_button(frame, TEMPLATE_MAIL, roi=mail_roi(frame))
        if ms is not None and ms >= MAIL_TH and mc:
            print(f"[邮箱] 点击「邮箱」图标（相似度 {ms:.3f}，坐标 {mc}），2s 后查领取…")
            a.adb_tap(mc[0], mc[1])
            time.sleep(2.0)
            continue
        print(f"[{i+1}] 未检测到邮箱图标，2s 后重试…")
        time.sleep(2)

    if not claimed:
        print("[测试] 多次尝试未检测到「领取全部」，失败")
        a.beep(False)
        return 1

    # 步骤A：点击「确认」（橙黄渐变，最多 3 轮）
    confirmed = False
    for _ in range(3):
        frame = a.capture_hdmi()
        if frame is None:
            time.sleep(1)
            continue
        ks, kc = a.detect_button(frame, TEMPLATE_MAIL_CONFIRM)
        if ks is not None and ks >= MAIL_CONFIRM_TH and kc:
            print(f"[确认] 点击「确认」（相似度 {ks:.3f}，坐标 {kc}），2s 后查「返回邮箱」…")
            a.adb_tap(kc[0], kc[1])
            time.sleep(2.0)
            confirmed = True
            break
        print(f"[确认] 未检测到「确认」按钮（第 {_+1} 轮），2s 后重试…")
        time.sleep(2)
    if not confirmed:
        print("[确认] 3 轮未检测到「确认」按钮，跳过确认步骤")

    # 步骤B：点击「返回邮箱」直到消失（新模板区分度大：界面 1.0 / 城镇 0.377）
    for j in range(10):
        frame = a.capture_hdmi()
        if frame is None:
            time.sleep(1)
            continue
        bs, bc = a.detect_button(frame, TEMPLATE_MAIL_BACK, roi=mail_back_roi(frame))
        if bs is not None and bs >= MAIL_BACK_TH and bc:
            print(f"[返回] 点击「返回邮箱」（相似度 {bs:.3f}，坐标 {bc}），2s 后复查…")
            a.adb_tap(bc[0], bc[1])
            time.sleep(2.0)
            continue
        print(f"[返回] 未检测到「返回邮箱」，已回到主页面（第 {j+1} 轮）✓")
        a.beep(True)
        return 0

    print("[测试] 10 轮「返回邮箱」仍存在，未回到主页面")
    a.beep(False)
    return 1


if __name__ == "__main__":
    sys.exit(main())
