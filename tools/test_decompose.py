# -*- coding: utf-8 -*-
"""分解装备流程逐步实测：背包 → 分解按钮 → 分解弹框 → 弹框内分解 → 提示弹窗
每步截图保存 images\\_decompose_N.png 并打印模板匹配结果，人工确认匹配率后写正式流程。"""
import os
import sys
import time
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auto_run as a

IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images")
os.makedirs(IMG_DIR, exist_ok=True)


def save(frame, name):
    p = os.path.join(IMG_DIR, name)
    cv2.imwrite(p, frame)
    print(f"  截图: {p}")


def probe(frame, tmpl_name, roi=None, th=0.55):
    s, c = a.detect_button(frame, os.path.join(a.IMG_DIR, tmpl_name), roi=roi)
    print(f"  [{tmpl_name}] {'未检测' if s is None else ('%.3f @%s' % (s, c))}")
    return s, c


def central_roi(frame):
    h, w = frame.shape[0], frame.shape[1]
    return (int(w * 0.15), int(h * 0.20), int(w * 0.85), int(h * 0.85))


print("=== 1) 当前画面（城镇主页） ===")
f = a.capture_hdmi()
save(f, "_decompose_0_home.png")
h, w = f.shape[0], f.shape[1]
probe(f, "template_bag.png", roi=(0, int(h * 0.6), w, h))
probe(f, "template_bag_back.png")

print("=== 2) 点「背包」图标 ===")
bs, bc = a.detect_button(f, os.path.join(a.IMG_DIR, "template_bag.png"), roi=(0, int(h * 0.6), w, h))
if bs is None or bs < 0.55 or not bc:
    print("  未检测到背包图标，手动输入坐标或退出"); sys.exit(1)
print(f"  点击背包 {bc}")
a.adb_tap(bc[0], bc[1])
time.sleep(2.0)
f = a.capture_hdmi()
save(f, "_decompose_1_bag.png")
probe(f, "template_decompose_btn.png")
probe(f, "template_bag.png", roi=(0, int(f.shape[0] * 0.6), f.shape[1], f.shape[0]))
probe(f, "template_bag_back.png")

print("=== 3) 点「分解」按钮 ===")
ds, dc = a.detect_button(f, os.path.join(a.IMG_DIR, "template_decompose_btn.png"))
if ds is None or ds < 0.55 or not dc:
    print("  未检测到分解按钮，退出"); sys.exit(1)
print(f"  点击分解按钮 {dc}")
a.adb_tap(dc[0], dc[1])
time.sleep(2.0)
f = a.capture_hdmi()
save(f, "_decompose_2_popup.png")
probe(f, "template_decompose_title.png")
probe(f, "template_decompose_go.png")
probe(f, "template_decompose_btn.png")

print("=== 4) 点弹框内金黄「分解」 ===")
gs, gc = a.detect_button(f, os.path.join(a.IMG_DIR, "template_decompose_go.png"))
if gs is None or gs < 0.55 or not gc:
    print("  未检测到弹框内分解按钮，退出"); sys.exit(1)
print(f"  点击金黄分解 {gc}")
a.adb_tap(gc[0], gc[1])
time.sleep(2.0)
f = a.capture_hdmi()
save(f, "_decompose_3_hint.png")
probe(f, "template_decompose_hint.png", roi=central_roi(f))
probe(f, "template_decompose_highvalue.png", roi=central_roi(f))
probe(f, "template_decompose_result.png", roi=central_roi(f))
probe(f, "template_decompose_confirm.png", roi=central_roi(f))

print("=== 结束（弹窗处理见下一轮测试） ===")
