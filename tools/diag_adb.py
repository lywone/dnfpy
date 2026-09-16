# -*- coding: utf-8 -*-
"""诊断 adb 截图链路：adb 路径 / 设备连接 / screencap -d 3 / pull"""
import glob
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auto_run as a

print("=" * 50)
print("[1] adb 路径")
adb = a.find_adb()
print(f"    find_adb() = {adb}")
print(f"    是否存在: {os.path.exists(adb)}")
if os.path.exists(adb):
    try:
        r = subprocess.run([adb, "version"], capture_output=True, text=True, timeout=20)
        print("    版本:", (r.stdout or r.stderr).strip().splitlines()[0])
    except Exception as e:
        print("    version 失败:", e)

print("[2] 设备列表")
try:
    r = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=30)
    print("    stdout:", r.stdout.strip())
    if r.stderr.strip():
        print("    stderr:", r.stderr.strip())
except Exception as e:
    print("    devices 失败:", e)

print("[3] 测试 screencap（分别尝试 -d 3 与默认 display）")
tmp_remote = "/sdcard/_dnfm_diag.png"
tmp_local = os.path.join(tempfile.gettempdir(), "_dnfm_diag.png")
for dev in ["127.0.0.1:5555", None]:
    base = [adb, "-s", dev] if dev else [adb]
    print(f"    设备: {dev or '(默认)'}")
    for disp in ["-d", "3", None]:
        cmd = base + ["shell", "screencap"] + (["-d", "3"] if disp else []) + ["-p", tmp_remote]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            ok = "OK" if r.returncode == 0 else f"RC={r.returncode}"
            err = (r.stderr or r.stdout).strip()[:120]
            print(f"      screencap {disp or '(默认)'}: {ok} {err}")
            if r.returncode == 0:
                r2 = subprocess.run([adb, "-s", dev, "pull", tmp_remote, tmp_local]
                                    if dev else [adb, "pull", tmp_remote, tmp_local],
                                    capture_output=True, text=True, timeout=60)
                import cv2
                img = cv2.imread(tmp_local)
                print(f"      pull: RC={r2.returncode} 文件={os.path.exists(tmp_local)} "
                      f"imread={'成功' if img is not None else '失败'} "
                      f"尺寸={None if img is None else (img.shape[1], img.shape[0])}")
                if img is not None:
                    print("      ✓ 截图链路可用")
                    sys.exit(0)
        except Exception as e:
            print(f"      异常: {e}")
print("未找到可用的截图链路")
