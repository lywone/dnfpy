# -*- coding: utf-8 -*-
"""诊断 SendInput 返回 0 的原因：结构体尺寸 / wVk 模式 / 扫描码模式 / keybd_event"""
import ctypes
import time

user32 = ctypes.windll.user32


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]
    _fields_ = [("type", ctypes.c_ulong), ("u", _U)]


KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

print(f"sizeof(KEYBDINPUT) = {ctypes.sizeof(KEYBDINPUT)} (期望 24)")
print(f"sizeof(INPUT)      = {ctypes.sizeof(INPUT)} (期望 32)")


def send(vk, scancode, flags):
    inp = INPUT()
    inp.type = 1
    inp.ki.wVk = vk
    inp.ki.wScan = scancode
    inp.ki.dwFlags = flags
    inp.ki.time = 0
    inp.ki.dwExtraInfo = 0
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


VK_Q = 0x51

# 1) wVk 模式
r1 = send(VK_Q, 0, 0)
r2 = send(VK_Q, 0, KEYEVENTF_KEYUP)
print(f"wVk 模式 down={r1} up={r2}")

# 2) 扫描码模式
sc = user32.MapVirtualKeyW(VK_Q, 0)
print(f"Q 的扫描码 = {sc}")
r3 = send(0, sc, KEYEVENTF_SCANCODE)
r4 = send(0, sc, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP)
print(f"扫描码模式 down={r3} up={r4}")

# 3) keybd_event 老 API
user32.keybd_event(VK_Q, 0, 0, 0)
time.sleep(0.05)
user32.keybd_event(VK_Q, 0, KEYEVENTF_KEYUP, 0)
print("keybd_event 完成（无返回值，看游戏是否响应）")

print("诊断完成")
