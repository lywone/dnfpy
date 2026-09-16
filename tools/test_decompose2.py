# -*- coding: utf-8 -*-
"""继续实测：点「确认」后弹窗序列（从当前弹窗状态开始，逐步点确认/关闭）"""
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
save(f, "_decomp_confirm_0_now.png")

print("=== 点「确认」(检测到的 0.825 @1241,955) ===")
a.adb_tap(1241, 955)
time.sleep(2.0)
f = a.capture_hdmi()
save(f, "_decomp_confirm_1.png")
probe(f, "template_decompose_confirm.png", roi=central_roi(f))
probe(f, "template_decompose_hint.png", roi=central_roi(f))
probe(f, "template_decompose_result.png", roi=central_roi(f))
probe(f, "template_decompose_highvalue.png", roi=central_roi(f))
probe(f, "template_decompose_title.png")
probe(f, "template_bag_back.png")

print("=== 若仍有确认按钮则再点 ===")
cs, cc = a.detect_button(f, os.path.join(a.IMG_DIR, "template_decompose_confirm.png"), roi=central_roi(f))
if cs is not None and cs >= 0.55 and cc:
    print(f"  再点确认 {cc}")
    a.adb_tap(cc[0], cc[1])
    time.sleep(2.0)
    f = a.capture_hdmi()
    save(f, "_decomp_confirm_2.png")
    probe(f, "template_decompose_confirm.png", roi=central_roi(f))
    probe(f, "template_decompose_result.png", roi=central_roi(f))
    probe(f, "template_decompose_title.png")
    probe(f, "template_bag_back.png")

print("=== 结束 ===")
