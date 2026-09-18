# -*- coding: utf-8 -*-
"""管理员复现：完整 press_esc 流程测试（当前弹窗画面）"""
import sys, time, ctypes, io
sys.path.insert(0, r'D:\code\dnfm-auto')
import auto_run as a
import cv2, numpy as np

log = io.open(r'C:\Users\lyyth\AppData\Local\Temp\_esc_repro_log.txt', 'w', encoding='utf-8')
def p(msg):
    log.write(msg + '\n')
    log.flush()

p('管理员: ' + str(bool(ctypes.windll.shell32.IsUserAnAdmin())))
prev = a.capture_hdmi()
if prev is not None:
    cv2.imwrite(r'C:\Users\lyyth\AppData\Local\Temp\_esc_repro_before.png', prev)
    p('before 截图 OK')
hwnd = a.find_game_window()
p('游戏窗口: ' + str(hwnd))
# 调用完整 press_esc
a.press_esc()
time.sleep(2.0)
f = a.capture_hdmi()
if f is not None:
    cv2.imwrite(r'C:\Users\lyyth\AppData\Local\Temp\_esc_repro_after.png', f)
    if prev is not None:
        p('press_esc 后像素差: ' + str(round(float(np.abs(prev.astype(float) - f.astype(float)).mean()), 2)))
p('DONE')
log.close()
