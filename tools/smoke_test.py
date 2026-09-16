# -*- coding: utf-8 -*-
"""Smoke test: load YOLOv5 ncnn model and run detection on bundled screenshots."""
import time
import cv2
from dnfm.yolov5 import YoloV5s

detector = YoloV5s(target_size=640, num_threads=4)
print("model loaded OK")

for name in ["1.png", "2.png", "3.png"]:
    img = cv2.imread(f"dnfm/img/{name}")
    if img is None:
        print(f"[skip] cannot read {name}")
        continue
    t0 = time.time()
    objs = detector(img)
    dt = (time.time() - t0) * 1000
    labels = {}
    for o in objs:
        labels[detector.class_names[int(o.label)]] = labels.get(
            detector.class_names[int(o.label)], 0
        ) + 1
    print(f"{name}: {len(objs)} detections in {dt:.0f}ms -> {labels}")
