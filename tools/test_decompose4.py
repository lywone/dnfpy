# -*- coding: utf-8 -*-
"""收尾实测：获得道具确认(1069,756) → 关闭分解框 → 背包返回主页
当前状态：获得道具弹窗开着"""
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


def central_roi(frame):
    h, w = frame.shape[0], frame.shape[1]
    return (int(w * 0.10), int(h * 0.10), int(w * 0.90), int(h * 0.90))


def probe(frame, tmpl_name, roi=None):
    s, c = a.detect_button(frame, os.path.join(a.IMG_DIR, tmpl_name), roi=roi)
    print(f"  [{tmpl_name}] {'未检测' if s is None else ('%.3f @%s' % (s, c))}")
    return s, c


print("=== 1) 点「获得道具」确认 (1069,756) ===")
a.adb_tap(1069, 756)
time.sleep(2.0)
f = a.capture_hdmi()
save(f, "_decomp4_1.png")
probe(f, "template_decompose_title.png")
probe(f, "template_decompose_result.png", roi=central_roi(f))
probe(f, "template_bag_back.png")

print("=== 2) 点 × 关闭分解弹框 (2038,126) ===")
a.adb_tap(2038, 126)
time.sleep(2.0)
f = a.capture_hdmi()
save(f, "_decomp4_2.png")
probe(f, "template_decompose_title.png")
probe(f, "template_decompose_btn.png")
probe(f, "template_bag_back.png")

print("=== 3) 点「背包返回」(96,40) ===")
bs, bc = a.detect_button(f, os.path.join(a.IMG_DIR, "template_bag_back.png"))
if bs is not None and bs >= 0.55 and bc:
    a.adb_tap(bc[0], bc[1])
    time.sleep(2.0)
f = a.capture_hdmi()
save(f, "_decomp4_3_home.png")
probe(f, "template_bag.png", roi=(0, int(f.shape[0] * 0.6), f.shape[1], f.shape[0]))
probe(f, "template_bag_back.png")
probe(f, "template_mail.png", roi=(0, int(f.shape[0] * 0.7), f.shape[1], f.shape[0]))

print("=== 结束（是否回到主页面？） ===")
