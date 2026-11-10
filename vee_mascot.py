"""Vee: a pixel desktop mascot that reacts to Claude (Windows).

Sources of state:
  1. Claude Code hooks  -> POST http://127.0.0.1:7777/event  (vee_hook.py)
                           GET  http://127.0.0.1:7777/<work|need|done|idle> also works
  2. Claude desktop Chat -> UI Automation watcher that looks for the Stop button

Run:  start_vee.bat   (or: pythonw vee_mascot.py)
"""

import ctypes
import datetime as dt
import json
import os
import random
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from sprites import COLS, DAYS, LID_MAX, PAL, ROWS, frame

VERSION = "0.7"
HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- settings
PORT = 7777
STOP_LABELS = {"Stop response", "Stop generating", "Stop"}
NEED_LABELS = {"Allow once", "Allow always", "Allow for this chat", "Always allow"}
POLL_SECONDS = 1.0
WORK_TIMEOUT = 10 * 60
DONE_TIMEOUT = 15 * 60
KEY = "#ff00ff"
CONFIG = HERE / "vee_config.json"
BUTTON_LOG = HERE / "vee_buttons.log"
ACTIVITY_LOG = HERE / "vee_activity.log"
CLAUDE_URL = "https://claude.ai"
NAME = "Vee"

DEFAULTS = {
    "x": None, "y": None, "scale": 4, "outfit": "auto",
    "progress": True, "prompt_text": False, "walk": True,
    "notify": True, "sound": True,
}

BUBBLE_BG = "#2b2a33"
BUBBLE_FG = "#f2f0ea"
BAR_BG = "#3a3944"
BAR_HOVER = "#55535f"
ICON_FONT = "Segoe MDL2 Assets"
ICON_EDIT, ICON_CHAT, ICON_MENU = "", "", ""

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

QUIT_REQUESTED = threading.Event()

DIAG = {"claude_windows": 0, "buttons_seen": 0, "watcher": "not started",
        "server": "not started", "last_hook": None}


def log_activity(msg):
    try:
        with ACTIVITY_LOG.open("a", encoding="utf-8") as f:
            f.write(dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S  ") + msg + "\n")
    except Exception:
        pass


def short(text, n=70):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def describe_tool(data):
    tool = data.get("tool_name") or ""
    inp = data.get("tool_input") or {}
    path = inp.get("file_path") or inp.get("path") or inp.get("notebook_path") or ""
    fname = Path(path).name if path else ""
    if tool == "Bash":
        return "Running " + short(inp.get("command", "a command"), 50)
    if tool in ("Edit", "MultiEdit", "Write", "NotebookEdit"):
        return f"Editing {fname or 'a file'}"
    if tool == "Read":
        return f"Reading {fname or 'a file'}"
    if tool in ("Grep", "Glob"):
        return "Searching files"
    if tool in ("WebSearch",):
        return "Searching the web"
    if tool in ("WebFetch",):
        return "Reading a web page"
    if tool in ("Task", "Agent"):
        return "Handing off to a helper"
    if tool.startswith("mcp__"):
        return "Using " + tool.split("__")[-1].replace("_", " ")
    return f"Using {tool}" if tool else "Working"


# ---------------------------------------------------------------- state
class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.hook = "idle"
        self.hook_ts = 0.0
        self.chat = "idle"
        self.done_at = 0.0
        self.progress = ""
        self.prompt = ""
        self.prompt_ts = 0.0
        self.need_msg = ""
        self.work_since = 0.0
        self.toast_need = 0.0

    def set_hook(self, s, data=None):
        data = data or {}
        with self.lock:
            now = time.time()
            if s == "work":
                if self.hook != "work":
                    self.work_since = now
                if data.get("prompt"):
                    self.prompt = data["prompt"]
                    self.prompt_ts = now
                    self.progress = "Reading your prompt"
                elif data.get("tool_name"):
                    self.progress = describe_tool(data)
            if s == "need":
                self.need_msg = data.get("message") or "Claude needs your permission"
            if s == "done":
                self.done_at = now
                self.hook = "idle"
            else:
                self.hook = s
            self.hook_ts = now

    def set_toast_need(self, msg):
        with self.lock:
            self.toast_need = time.time()
            self.need_msg = msg

    def clear_toast_need(self):
        with self.lock:
            self.toast_need = 0.0

    def set_chat(self, s):
        with self.lock:
            if self.chat in ("work", "need") and s == "idle":
                self.toast_need = 0.0   # task ended, so the request is gone
            if self.chat == "work" and s == "idle":
                self.done_at = time.time()
            if self.chat != "work" and s == "work":
                self.work_since = time.time()
            if s == "need":
                self.need_msg = "Claude needs your permission"
            self.chat = s

    def clear_done(self):
        with self.lock:
            self.done_at = 0.0

    def snapshot(self):
        with self.lock:
            now = time.time()
            if self.hook in ("work", "need") and now - self.hook_ts > WORK_TIMEOUT:
                self.hook = "idle"
            if self.toast_need and now - self.toast_need > WORK_TIMEOUT:
                self.toast_need = 0.0
            states = {self.hook, self.chat}
            if self.toast_need:
                states.add("need")
            if "need" in states:
                st = "need"
            elif "work" in states:
                st = "work"
            elif self.done_at and now - self.done_at < DONE_TIMEOUT:
                st = "done"
            else:
                st = "idle"
            if st == "work":
                if self.hook == "work" and self.progress:
                    detail = self.progress
                else:
                    secs = int(now - (self.work_since or now))
                    detail = f"Thinking… {secs // 60}:{secs % 60:02d}"
            elif st == "need":
                detail = self.need_msg
            else:
                detail = ""
            prompt = self.prompt if now - self.prompt_ts < 6 else ""
            return st, detail, prompt


STATE = State()


# ---------------------------------------------------------------- hooks server
class Handler(BaseHTTPRequestHandler):
    def _ok(self, code=204):
        self.send_response(code)
        self.end_headers()

    def do_GET(self):
        s = self.path.strip("/").split("?")[0]
        if s == "ping":
            return self._ok(200)
        if s == "quit":
            QUIT_REQUESTED.set()
            return self._ok(200)
        if s in ("work", "need", "done", "idle"):
            STATE.set_hook(s)
            DIAG["last_hook"] = f"{s} @ {time.strftime('%H:%M:%S')}"
            self._ok()
        else:
            self._ok(404)

    def do_POST(self):
        if self.path.strip("/") != "event":
            return self.do_GET()
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            s = body.get("state", "idle")
            if s in ("work", "need", "done", "idle"):
                STATE.set_hook(s, body.get("data") or {})
                DIAG["last_hook"] = f"{s} @ {time.strftime('%H:%M:%S')}"
            self._ok()
        except Exception:
            self._ok(400)

    def log_message(self, *a):
        pass


def run_server():
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
        DIAG["server"] = f"listening on {PORT}"
        srv.serve_forever()
    except OSError as e:
        DIAG["server"] = f"failed: {e}"


# ---------------------------------------------------------------- chat watcher
def find_claude(auto):
    wins = []
    for w in auto.GetRootControl().GetChildren():
        try:
            if w.ClassName == "Chrome_WidgetWin_1" and w.Name.strip().startswith("Claude"):
                wins.append(w)
        except Exception:
            continue
    return wins


def run_watcher():
    try:
        import uiautomation as auto
    except ImportError:
        DIAG["watcher"] = "uiautomation not installed"
        return
    DIAG["watcher"] = "running"
    with auto.UIAutomationInitializerInThread():
        seen = set()
        while True:
            try:
                wins = find_claude(auto)
                DIAG["claude_windows"] = len(wins)
                names = set()
                for win in wins:
                    for c, _ in auto.WalkControl(win, maxDepth=60):
                        if c.ControlTypeName == "ButtonControl" and c.Name:
                            names.add(c.Name.strip())
                new = names - seen
                if new and len(seen) < 400:
                    seen |= new
                    DIAG["buttons_seen"] = len(seen)
                    try:
                        with BUTTON_LOG.open("a", encoding="utf-8") as f:
                            f.write(time.strftime("%H:%M:%S ") + " | ".join(sorted(new)) + "\n")
                    except Exception:
                        pass
                if names & NEED_LABELS:
                    STATE.set_chat("need")
                elif names & STOP_LABELS:
                    STATE.set_chat("work")
                else:
                    STATE.set_chat("idle")
            except Exception as e:
                DIAG["watcher"] = f"error: {e}"
            time.sleep(POLL_SECONDS)


# ---------------------------------------------------------------- notification watcher
NOTIFY_DB = Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Notifications\wpndatabase.db"))
NEED_PHRASES = ("needs permission", "needs your permission", "needs your input",
                "needs your approval", "wants to use", "waiting for your input")


def _notify_rows(sql, args):
    """Read the Windows notification history. Tries a read-only open, then a copy."""
    import sqlite3
    try:
        con = sqlite3.connect(f"file:{NOTIFY_DB.as_posix()}?mode=ro", uri=True, timeout=1)
        try:
            return con.execute(sql, args).fetchall()
        finally:
            con.close()
    except Exception:
        import shutil, tempfile
        tmp = Path(tempfile.gettempdir()) / "vee_wpn.db"
        for ext in ("", "-wal", "-shm"):
            src = Path(str(NOTIFY_DB) + ext)
            if src.exists():
                shutil.copy2(src, str(tmp) + ext)
        con = sqlite3.connect(str(tmp))
        try:
            return con.execute(sql, args).fetchall()
        finally:
            con.close()


def run_notify_watcher():
    """Claude posts a Windows toast when it needs permission or input while in the
    background. The window itself stops updating then, so this is the reliable signal."""
    import re
    if not NOTIFY_DB.exists():
        DIAG["notify"] = "no notification database"
        return
    try:
        handlers = [r for (r, p) in _notify_rows("SELECT RecordId, PrimaryId FROM NotificationHandler", ())
                    if p and p.lower().startswith("claude_") and p.lower().endswith("!claude")]
        if not handlers:
            DIAG["notify"] = "no Claude notification handler"
            return
        marks = ",".join("?" * len(handlers))
        last = _notify_rows(f"SELECT IFNULL(MAX(Id),0) FROM Notification WHERE HandlerId IN ({marks})", handlers)[0][0]
        DIAG["notify"] = "running"
    except Exception as e:
        DIAG["notify"] = f"error: {e}"
        return
    stamp = None
    while True:
        try:
            files = [Path(str(NOTIFY_DB) + ext) for ext in ("", "-wal")]
            now_stamp = tuple(f.stat().st_mtime for f in files if f.exists())
            if now_stamp != stamp:
                stamp = now_stamp
                rows = _notify_rows(
                    f"SELECT Id, Payload FROM Notification WHERE HandlerId IN ({marks}) AND Id > ? ORDER BY Id",
                    handlers + [last])
                for nid, payload in rows:
                    last = max(last, nid)
                    text = payload.decode("utf-8", "ignore") if isinstance(payload, bytes) else str(payload)
                    parts = [re.sub(r"<[^>]+>", "", t).strip() for t in re.findall(r"<text[^>]*>(.*?)</text>", text, re.S)]
                    body = " · ".join(p for p in parts if p)
                    if any(k in body.lower() for k in NEED_PHRASES):
                        msg = parts[-1] if parts else "Claude needs you"
                        STATE.set_toast_need(msg)
                        log_activity(f"notification: {body}")
            DIAG["notify"] = "running"
        except Exception as e:
            DIAG["notify"] = f"error: {e}"
        time.sleep(1.0)


# ---------------------------------------------------------------- windows helpers
def foreground_title():
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        return buf.value.strip()
    except Exception:
        return ""


def claude_focused():
    return foreground_title().startswith("Claude")


def work_area():
    try:
        class RECT(ctypes.Structure):
            _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                        ("r", ctypes.c_long), ("b", ctypes.c_long)]
        r = RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)
        return r.l, r.t, r.r, r.b
    except Exception:
        return None


def virtual_screen():
    """Bounds of all monitors together (left, top, right, bottom)."""
    try:
        m = ctypes.windll.user32.GetSystemMetrics
        x, y = m(76), m(77)
        return x, y, x + m(78), y + m(79)
    except Exception:
        return None


def focus_claude():
    """Bring the Claude desktop window to the front, or open claude.ai."""
    try:
        user32 = ctypes.windll.user32
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def cb(hwnd, _):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value.strip() == "Claude" and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True

        user32.EnumWindows(cb, 0)
        if found:
            user32.ShowWindow(found[0], 9)
            user32.SetForegroundWindow(found[0])
            return
    except Exception:
        pass
    webbrowser.open(CLAUDE_URL)


def toast(title, body):
    def esc(s):
        return str(s).replace("'", "''")
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
        "$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
        "$x=$t.GetElementsByTagName('text');"
        f"$x.Item(0).AppendChild($t.CreateTextNode('{esc(title)}')) > $null;"
        f"$x.Item(1).AppendChild($t.CreateTextNode('{esc(body)}')) > $null;"
        "$n=[Windows.UI.Notifications.ToastNotification]::new($t);"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
        "'{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe').Show($n)"
    )
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                         creationflags=0x08000000)
    except Exception:
        pass


def chime():
    try:
        import winsound
        winsound.PlaySound("SystemNotification", winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        pass


# ---------------------------------------------------------------- window
class Mascot:
    BUBBLE_H = 110  # space above the pet for the bubble and toolbar

    def __init__(self):
        self.cfg = dict(DEFAULTS)
        if CONFIG.exists():
            try:
                saved = json.loads(CONFIG.read_text())
                if "progress" not in saved:  # position from the old, smaller window
                    saved.pop("x", None); saved.pop("y", None)
                self.cfg.update(saved)
            except Exception:
                pass
        self.t = 0
        self.focus_since = None
        self.last_state = "idle"
        self.bubble_text = ""
        self.bubble_until = 0.0
        self.bubble_sticky = False
        self.hover_until = 0.0
        self.hover_btn = None
        self.walk = None
        self.flip = False
        self.lid = 0
        self.press = None
        self.dragging = False
        self.ui_sig = None

        self.root = tk.Tk()
        self.root.title(NAME)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", KEY)
        self.root.configure(bg=KEY)
        self.canvas = tk.Canvas(self.root, bg=KEY, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.font = tkfont.Font(family="Segoe UI", size=10)
        self.icon_font = tkfont.Font(family=ICON_FONT, size=11)

        self.vars = {k: tk.BooleanVar(value=bool(self.cfg[k]))
                     for k in ("progress", "prompt_text", "walk", "notify", "sound")}
        self.build_cells()
        self.place()

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", lambda e: self.menu(e.x_root, e.y_root))
        self.say(f"{NAME} says hi!", 4)
        log_activity(f"{NAME} started (v{VERSION})")
        self.tick()

    # ---------- geometry
    @property
    def s(self):
        return self.cfg["scale"]

    @property
    def W(self):
        return max(300, COLS * self.s + 40)

    @property
    def H(self):
        return self.BUBBLE_H + ROWS * self.s

    def pet_origin(self):
        return (self.W - COLS * self.s) // 2, self.BUBBLE_H

    def build_cells(self):
        s = self.s
        self.canvas.delete("all")
        self.canvas.config(width=self.W, height=self.H)
        ox, oy = self.pet_origin()
        self.cells = [[self.canvas.create_rectangle(ox + c * s, oy + r * s, ox + c * s + s, oy + r * s + s,
                                                    width=0, fill=KEY, state="hidden", tags="pet")
                       for c in range(COLS)] for r in range(ROWS)]
        self.last = [["?"] * COLS for _ in range(ROWS)]
        self.ui_sig = None

    def default_pos(self):
        wa = work_area()
        if wa:
            l, t, r, b = wa
            return r - self.W - 20, b - self.H
        return (self.root.winfo_screenwidth() - self.W - 40,
                self.root.winfo_screenheight() - self.H - 60)

    def place(self):
        x, y = self.cfg["x"], self.cfg["y"]
        if x is None or y is None:
            x, y = self.default_pos()
        self.x, self.y = int(x), int(y)
        self.root.geometry(f"{self.W}x{self.H}+{self.x}+{self.y}")
        self.ensure_visible()

    def ensure_visible(self):
        """Bring her back if a display change left her pet sprite off every screen."""
        vs = virtual_screen()
        if not vs:
            return
        x0, y0, x1, y1 = self.pet_rect()
        px0, py0, px1, py1 = self.x + x0, self.y + y0, self.x + x1, self.y + y1
        l, t, r, b = vs
        if px0 < l or py0 < t or px1 > r or py1 > b:
            x, y = self.default_pos()
            self.move_to(x, y)
            self.cfg["x"], self.cfg["y"] = x, y
            self.save()
            log_activity("was off-screen, moved back")

    def move_to(self, x, y):
        self.x, self.y = int(x), int(y)
        self.root.geometry(f"+{self.x}+{self.y}")

    def bring_back(self):
        self.walk = None
        x, y = self.default_pos()
        self.move_to(x, y)
        self.cfg["x"], self.cfg["y"] = x, y
        self.save()
        self.say("I'm back!", 3)

    # ---------- bubble + toolbar
    def say(self, text, seconds=4, sticky=False):
        self.bubble_text = text
        self.bubble_sticky = sticky
        self.bubble_until = time.time() + seconds

    def bubble_visible(self):
        return bool(self.bubble_text) and (self.bubble_sticky or time.time() < self.bubble_until)

    def toolbar_buttons(self):
        cx = self.W // 2
        y0, y1 = self.BUBBLE_H - 42, self.BUBBLE_H - 10
        bw = 34
        x0 = cx - (bw * 3) // 2
        return [("edit", ICON_EDIT, x0, y0, x0 + bw, y1),
                ("chat", ICON_CHAT, x0 + bw, y0, x0 + 2 * bw, y1),
                ("menu", ICON_MENU, x0 + 2 * bw, y0, x0 + 3 * bw, y1)]

    def pet_rect(self):
        ox, oy = self.pet_origin()
        return ox, oy, ox + COLS * self.s, oy + ROWS * self.s

    def draw_ui(self, show_bar):
        bubble = self.bubble_text if self.bubble_visible() else ""
        sig = (bubble, show_bar, self.hover_btn, self.W)
        if sig == self.ui_sig:
            return
        self.ui_sig = sig
        c = self.canvas
        c.delete("ui")
        if show_bar:
            for name, icon, x0, y0, x1, y1 in self.toolbar_buttons():
                fill = BAR_HOVER if self.hover_btn == name else BAR_BG
                self.round_rect(x0 + 1, y0, x1 - 1, y1, 8, fill)
                c.create_text((x0 + x1) // 2, (y0 + y1) // 2, text=icon, fill=BUBBLE_FG,
                              font=self.icon_font, tags="ui")
        if bubble:
            bottom = self.BUBBLE_H - (48 if show_bar else 8)
            tid = c.create_text(self.W // 2 + 8, bottom - 6, text=bubble, fill=BUBBLE_FG,
                                font=self.font, width=self.W - 60, anchor="s", justify="left", tags="ui")
            x0, y0, x1, y1 = c.bbox(tid)
            dx = self.W // 2 - ((x0 - 26) + (x1 + 12)) // 2
            c.move(tid, dx, 0)
            x0, y0, x1, y1 = c.bbox(tid)
            self.round_rect(x0 - 26, y0 - 7, x1 + 12, y1 + 6, 12, BUBBLE_BG, below=tid)
            dot = "#EF9F27" if self.last_state == "need" else ("#D4537E" if self.last_state == "done" else "#7F77DD")
            c.create_oval(x0 - 17, (y0 + y1) // 2 - 4, x0 - 9, (y0 + y1) // 2 + 4, fill=dot, width=0, tags="ui")
        c.tag_raise("pet")

    def round_rect(self, x0, y0, x1, y1, r, fill, below=None):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        item = self.canvas.create_polygon(pts, smooth=True, fill=fill, outline="", tags="ui")
        if below is not None:
            self.canvas.tag_lower(item, below)
        return item

    # ---------- mouse
    def local_pointer(self):
        px, py = self.root.winfo_pointerxy()
        return px - self.x, py - self.y

    def hit(self, x, y):
        if self.hover_until > time.time():
            for name, _, x0, y0, x1, y1 in self.toolbar_buttons():
                if x0 <= x <= x1 and y0 <= y <= y1:
                    return name
        x0, y0, x1, y1 = self.pet_rect()
        if x0 <= x <= x1 and y0 <= y <= y1:
            return "pet"
        return None

    def on_press(self, e):
        self.press = (e.x_root, e.y_root, self.x, self.y, self.hit(e.x, e.y))
        self.dragging = False

    def on_motion(self, e):
        if not self.press or self.press[4] != "pet":
            return
        dx, dy = e.x_root - self.press[0], e.y_root - self.press[1]
        if abs(dx) + abs(dy) > 4:
            self.dragging = True
            self.walk = None
            self.move_to(self.press[2] + dx, self.press[3] + dy)

    def on_release(self, e):
        if not self.press:
            return
        target = self.press[4]
        if self.dragging:
            self.cfg["x"], self.cfg["y"] = self.x, self.y
            self.save()
        elif target == "edit":
            focus_claude()
        elif target == "chat":
            self.toggle("progress")
            on = self.cfg["progress"]
            self.say(f"Progress updates {'on' if on else 'off'} · Done and alerts still show", 3)
        elif target == "menu":
            self.menu(e.x_root, e.y_root)
        elif target == "pet":
            self.say(random.choice([f"{NAME} says hi!", "Hehe", "Need something?", "I'm here"]), 3)
        self.press = None
        self.dragging = False

    # ---------- walking
    def update_walk(self, state, hovering):
        can_walk = (self.cfg["walk"] and state in ("idle", "done") and not hovering and not self.lid
                    and not self.dragging and not self.bubble_visible())
        if not can_walk:
            self.walk = None
            return
        wa = work_area() or (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        left, right = wa[0] - (self.W - COLS * self.s) // 2, wa[2] - self.W + (self.W - COLS * self.s) // 2
        if self.walk is None:
            if random.random() < 0.006:
                d = random.choice((-1, 1))
                if self.x + d * 150 < left or self.x + d * 150 > right:
                    d = -d
                self.walk = {"dir": d, "left": random.randint(80, 320)}
                self.flip = d < 0
            return
        step = max(2, self.s)
        nx = self.x + self.walk["dir"] * step
        if nx < left or nx > right:
            self.walk = None
            return
        self.move_to(nx, self.y)
        self.walk["left"] -= step
        if self.walk["left"] <= 0:
            self.walk = None
            self.cfg["x"], self.cfg["y"] = self.x, self.y
            self.save()

    # ---------- main loop
    def day(self):
        o = self.cfg["outfit"]
        return DAYS.index(o) if o in DAYS else dt.date.today().weekday()

    def on_state_change(self, old, new, detail):
        log_activity(f"{old} -> {new}" + (f"  ({detail})" if detail else ""))
        if new == "done":
            self.say("Done! Claude finished.", 6)
            if not claude_focused():
                if self.cfg["notify"]:
                    toast(f"{NAME}: Claude is done", "Your reply is ready.")
                if self.cfg["sound"]:
                    chime()
        elif new == "need":
            self.say(short(detail or "Claude needs your permission", 90), 5, sticky=True)
            if self.cfg["sound"]:
                chime()   # Claude already shows its own notification for this
        elif new == "work":
            self.bubble_sticky = False
        elif new == "idle" and old in ("work", "need"):
            self.bubble_sticky = False
            self.bubble_until = 0

    def tick(self):
        try:
            self._tick()
        except Exception as e:
            log_activity(f"tick error: {e}")
        if not QUIT_REQUESTED.is_set():
            self.root.after(100, self.tick)

    def _tick(self):
        if QUIT_REQUESTED.is_set():
            self.quit()
            return
        state, detail, prompt = STATE.snapshot()
        if state != self.last_state:
            old, self.last_state = self.last_state, state
            self.on_state_change(old, state, detail)

        if state == "work":
            if self.cfg["prompt_text"] and prompt:
                self.say("You: " + short(prompt, 90), 1, sticky=True)
            elif self.cfg["progress"]:
                self.say(short(detail, 90), 1, sticky=True)
            elif self.bubble_sticky:
                self.bubble_sticky = False
                self.bubble_until = 0
        elif state == "need":
            self.say(short(detail or "Claude needs your permission", 90), 1, sticky=True)

        if claude_focused():
            STATE.clear_toast_need()   # window is live again, the watcher takes over
        if state == "done":
            if claude_focused():
                self.focus_since = self.focus_since or time.time()
                if time.time() - self.focus_since > 3:
                    STATE.clear_done()
            else:
                self.focus_since = None
        else:
            self.focus_since = None

        lx, ly = self.local_pointer()
        over = self.hit(lx, ly)
        if over == "pet" or (over in ("edit", "chat", "menu")):
            self.hover_until = time.time() + 1.5
        hovering = time.time() < self.hover_until
        self.hover_btn = over if over in ("edit", "chat", "menu") else None

        # laptop: opens while Claude works or waits on you, closes after
        target = LID_MAX if state in ("work", "need") else 0
        if self.lid < target:
            self.lid += 1
        elif self.lid > target:
            self.lid -= 1
        if self.lid:
            self.flip = False

        self.update_walk(state, hovering)

        if self.t % 50 == 0 and not self.dragging:
            self.ensure_visible()
        if self.t % 20 == 0:
            try:
                if self.root.state() != "normal":
                    self.root.deiconify()
                self.root.attributes("-topmost", True)
            except Exception:
                pass

        F = frame(self.day(), state, self.t, walking=self.walk is not None, flip=self.flip, lid=self.lid)
        for r in range(ROWS):
            for c in range(COLS):
                ch = F[r][c]
                if ch != self.last[r][c]:
                    if ch == "." or ch not in PAL:
                        self.canvas.itemconfig(self.cells[r][c], state="hidden")
                    else:
                        self.canvas.itemconfig(self.cells[r][c], fill=PAL[ch], state="normal")
                    self.last[r][c] = ch
        self.draw_ui(hovering)
        self.t += 1

    # ---------- config + menu
    def save(self):
        try:
            CONFIG.write_text(json.dumps(self.cfg, indent=2))
        except Exception:
            pass

    def toggle(self, key):
        self.cfg[key] = not self.cfg[key]
        self.vars[key].set(self.cfg[key])
        self.save()

    def set_cfg(self, k, v):
        self.cfg[k] = v
        self.save()
        if k == "scale":
            self.build_cells()
            self.root.geometry(f"{self.W}x{self.H}")
        if k == "outfit":
            self.say(f"Wearing my {v if v in DAYS else 'today'} look", 3)

    def var_changed(self, key):
        self.cfg[key] = bool(self.vars[key].get())
        self.save()

    def copy_diagnostics(self):
        st, detail, _ = STATE.snapshot()
        lines = [
            f"{NAME} v{VERSION}",
            f"python: {sys.executable} ({sys.version.split()[0]})",
            f"folder: {HERE}",
            f"state: {st} {detail}",
            f"hook server: {DIAG['server']}",
            f"last hook: {DIAG['last_hook']}",
            f"chat watcher: {DIAG['watcher']}",
            f"notification watcher: {DIAG.get('notify')}",
            f"claude windows: {DIAG['claude_windows']}",
            f"distinct buttons seen: {DIAG['buttons_seen']}",
            f"foreground: {foreground_title()}",
            f"config: {json.dumps(self.cfg)}",
        ]
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(lines))
        self.say("Diagnostics copied", 3)

    def open_log(self):
        if not ACTIVITY_LOG.exists():
            log_activity("log created")
        try:
            os.startfile(str(ACTIVITY_LOG))
        except Exception:
            pass

    def menu(self, x, y):
        m = tk.Menu(self.root, tearoff=0)
        m.add_command(label=NAME, state="disabled")
        om = tk.Menu(m, tearoff=0)
        om.add_command(label="Auto (by weekday)", command=lambda: self.set_cfg("outfit", "auto"))
        for d in DAYS:
            om.add_command(label=d, command=lambda d=d: self.set_cfg("outfit", d))
        m.add_cascade(label="Choose outfit", menu=om)
        m.add_separator()
        labels = [("progress", "Show progress updates"), ("prompt_text", "Show prompt text"),
                  ("walk", "Walk around"), ("notify", "Notify when Claude is done"),
                  ("sound", "Sound when Claude is done")]
        for key, label in labels:
            m.add_checkbutton(label=label, variable=self.vars[key],
                              command=lambda k=key: self.var_changed(k))
        sm = tk.Menu(m, tearoff=0)
        for s in (2, 3, 4, 5, 6):
            sm.add_command(label=f"{s}x", command=lambda s=s: self.set_cfg("scale", s))
        m.add_cascade(label="Size", menu=sm)
        m.add_separator()
        m.add_command(label="Open in browser", command=lambda: webbrowser.open(CLAUDE_URL))
        m.add_command(label="Open activity log", command=self.open_log)
        m.add_command(label="Test the Done message", command=lambda: STATE.set_hook("done"))
        tm = tk.Menu(m, tearoff=0)
        for s in ("idle", "work", "need", "done"):
            tm.add_command(label=s, command=lambda s=s: STATE.set_hook(s))
        m.add_cascade(label="Test state", menu=tm)
        m.add_command(label="Copy diagnostics", command=self.copy_diagnostics)
        m.add_command(label="Bring pet back", command=self.bring_back)
        m.add_separator()
        m.add_command(label="Quit", command=self.quit)
        m.tk_popup(x, y)

    def quit(self):
        QUIT_REQUESTED.set()
        log_activity(f"{NAME} quit")
        try:
            self.root.destroy()
        except Exception:
            pass


def already_running():
    import urllib.request
    import urllib.error
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/ping", timeout=1)
        return True
    except urllib.error.HTTPError:
        return True   # an older Vee is answering on the port
    except Exception:
        return False


if __name__ == "__main__":
    if already_running():
        sys.exit(0)   # one Vee at a time
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=run_watcher, daemon=True).start()
    threading.Thread(target=run_notify_watcher, daemon=True).start()
    Mascot().root.mainloop()
