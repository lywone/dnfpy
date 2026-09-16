# -*- coding: utf-8 -*-
"""背包界面 → 城镇 返回方法实测（当前状态：背包主界面）"""
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


def is_home(frame):
    h, w = frame.shape[0], frame.shape[1]
    m1, _ = a.detect_button(frame, os.path.join(a.IMG_DIR, "template_mail.png"), roi=(0, int(h * 0.7), w, h))
    s1, _ = a.detect_button(frame, os.path.join(a.IMG_DIR, "template_shop.png"), roi=(int(w * 0.5), 0, w, int(h * 0.2)))
    b1, _ = a.detect_button(frame, os.path.join(a.IMG_DIR, "template_bag.png"), roi=(0, int(h * 0.6), w, h))
    return (m1 is not None and m1 >= 0.55) or (s1 is not None and s1 >= 0.55)


print("=== 0) 当前（背包界面） ===")
f = a.capture_hdmi()
save(f, "_decomp6_0.png")
probe(f, "template_bag.png", roi=(0, int(f.shape[0] * 0.6), f.shape[1], f.shape[0]))
probe(f, "template_mail.png", roi=(0, int(f.shape[0] * 0.7), f.shape[1], f.shape[0]))

print("=== 1) BACK (keyevent 4) ===")
a.adb_back()
time.sleep(2.0)
f = a.capture_hdmi()
save(f, "_decomp6_1_back.png")
probe(f, "template_bag.png", roi=(0, int(f.shape[0] * 0.6), f.shape[1], f.shape[0]))
probe(f, "template_mail.png", roi=(0, int(f.shape[0] * 0.7), f.shape[1], f.shape[0]))
probe(f, "template_shop.png", roi=(int(f.shape[0] * 0.5), 0, f.shape[1], int(f.shape[1] * 0.2)))
print("  是否回到城镇主页:", is_home(f))

print("=== 2) 若还在背包，再 BACK ===")
if not is_home(f):
    a.adb_back()
    time.sleep(2.0)
    f = a.capture_hdmi()
    save(f, "_decomp6_2_back2.png")
    probe(f, "template_bag.png", roi=(0, int(f.shape[0] * 0.6), f.shape[1], f.shape[0]))
    probe(f, "template_mail.png", roi=(0, int(f.shape[0] * 0.7), f.shape[1], f.shape[0]))
    probe(f, "template_shop.png", roi=(int(f.shape[0] * 0.5), 0, f.shape[1], int(f.shape[1] * 0.2)))
    print("  是否回到城镇主页:", is_home(f))

print("=== 结束 ===")
