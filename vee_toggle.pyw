"""Ctrl+Alt+M target: closes every running Vee if any is running, otherwise starts one."""
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
NO_WINDOW = 0x08000000


def vee_pids():
    """Process ids of any python running vee_mascot.py (any version)."""
    ps = ("Get-CimInstance Win32_Process -Filter \"name='pythonw.exe' or name='python.exe'\" | "
          "Where-Object { $_.CommandLine -match 'vee_mascot\\.py' } | "
          "ForEach-Object { $_.ProcessId }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True,
                             text=True, timeout=15, creationflags=NO_WINDOW).stdout
        return [int(x) for x in out.split() if x.strip().isdigit()]
    except Exception:
        return []


def ask(path):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:7777/{path}", timeout=1)
        return True
    except urllib.error.HTTPError:
        return True     # an older Vee answered
    except Exception:
        return False


pids = vee_pids()
if pids or ask("ping"):
    ask("quit")                     # lets the current version close cleanly
    time.sleep(1.0)
    for pid in vee_pids():          # older versions, or extra copies
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, creationflags=NO_WINDOW)
else:
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = str(pyw if pyw.exists() else sys.executable)
    subprocess.Popen([exe, str(HERE / "vee_mascot.py")], cwd=str(HERE),
                     creationflags=0x00000008 | 0x00000200)
