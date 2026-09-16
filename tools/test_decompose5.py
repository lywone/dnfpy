# -*- coding: utf-8 -*-
"""关闭分解界面 → 返回城镇 方法实测
当前状态：分解界面「没有可选择的道具」（分解完成空状态）"""
import os
import sys
import time
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auto_run as a

IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images")


def save(frame, name):
    p = os.path.join(IMG_DIR, name)
    cv2.imwrite(p, frame)
    print(f"  截图: {p}")


def probe(frame, tmpl_name, roi=None):
    s, c = a.detect_button(frame, os.path.join(a.IMG_DIR, tmpl_name), roi=roi)
    print(f"  [{tmpl_name}] {'未检测' if s is None else ('%.3f @%s' % (s, c))}")
    return s, c


print("=== 0) 当前状态 ===")
f = a.capture_hdmi()
save(f, "_decomp5_0.png")
probe(f, "template_decompose_title.png")
probe(f, "template_decompose_btn.png")
probe(f, "template_bag.png")
probe(f, "template_bag_back.png")

print("=== 1) 点 × (2035,134) ===")
a.adb_tap(2035, 134)
time.sleep(2.0)
f = a.capture_hdmi()
save(f, "_decomp5_1_after_x.png")
probe(f, "template_decompose_title.png")
probe(f, "template_decompose_btn.png")
probe(f, "template_bag.png")
probe(f, "template_bag_back.png")

print("=== 2) BACK keyevent 4 ===")
a.adb_back()
time.sleep(2.0)
f = a.capture_hdmi()
save(f, "_decomp5_2_after_back.png")
probe(f, "template_decompose_title.png")
probe(f, "template_bag.png")
probe(f, "template_bag_back.png")
probe(f, "template_mail.png", roi=(0, int(f.shape[0] * 0.7), f.shape[1], f.shape[0]))
probe(f, "template_shop.png", roi=(int(f.shape[0] * 0.5), 0, f.shape[1], int(f.shape[1] * 0.2)))

print("=== 3) 若还在背包界面，再 BACK ===")
f = a.capture_hdmi()
bs, bc = a.detect_button(f, os.path.join(a.IMG_DIR, "template_bag.png"), roi=(0, int(f.shape[0] * 0.6), f.shape[1], f.shape[0]))
ts, tc = a.detect_button(f, os.path.join(a.IMG_DIR, "template_decompose_title.png"))
if (bs is None or bs < 0.55) and (ts is None or ts < 0.55):
    print("  已不在背包/分解界面（可能已回城镇）")
else:
    print("  仍在背包/分解界面，再按 BACK…")
    a.adb_back()
    time.sleep(2.0)
    f = a.capture_hdmi()
    save(f, "_decomp5_3.png")
    probe(f, "template_bag.png", roi=(0, int(f.shape[0] * 0.6), f.shape[1], f.shape[0]))
    probe(f, "template_mail.png", roi=(0, int(f.shape[0] * 0.7), f.shape[1], f.shape[0]))
    probe(f, "template_shop.png", roi=(int(f.shape[0] * 0.5), 0, f.shape[1], int(f.shape[1] * 0.2)))

print("=== 结束 ===")
