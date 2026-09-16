# -*- coding: utf-8 -*-
"""继续实测：外层确认(1241,955) → 内层高价值确认(1235,751) → 分解结果
当前状态：弹窗仍在（上层组合弹窗状态）"""
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


f = a.capture_hdmi()
save(f, "_decomp3_0.png")
probe(f, "template_decompose_confirm.png", roi=central_roi(f))

print("=== 点外层确认 (1241,955) ===")
a.adb_tap(1241, 955)
time.sleep(1.5)
f = a.capture_hdmi()
save(f, "_decomp3_1_inner.png")
probe(f, "template_decompose_highvalue.png", roi=central_roi(f))
probe(f, "template_decompose_confirm.png", roi=central_roi(f))
probe(f, "template_decompose_title.png")

print("=== 点内层确认 (1235,751) ===")
a.adb_tap(1235, 751)
time.sleep(2.5)
f = a.capture_hdmi()
save(f, "_decomp3_2_result.png")
probe(f, "template_decompose_confirm.png", roi=central_roi(f))
probe(f, "template_decompose_result.png", roi=central_roi(f))
probe(f, "template_decompose_highvalue.png", roi=central_roi(f))
probe(f, "template_decompose_title.png")
probe(f, "template_bag_back.png")

print("=== 若还有确认则再点一次（获得道具弹窗） ===")
cs, cc = a.detect_button(f, os.path.join(a.IMG_DIR, "template_decompose_confirm.png"), roi=central_roi(f))
if cs is not None and cs >= 0.55 and cc and abs(cc[1] - 955) > 100:
    print(f"  再点确认 {cc}")
    a.adb_tap(cc[0], cc[1])
    time.sleep(2.0)
    f = a.capture_hdmi()
    save(f, "_decomp3_3.png")
    probe(f, "template_decompose_confirm.png", roi=central_roi(f))
    probe(f, "template_decompose_title.png")
    probe(f, "template_bag_back.png")

print("=== 结束 ===")
