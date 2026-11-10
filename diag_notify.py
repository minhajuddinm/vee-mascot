"""Checks whether Claude's Windows notifications can be read. Only Claude rows are written out."""
import os, re, sqlite3, shutil, tempfile, traceback

out = open("diag_notify.txt", "w", encoding="utf-8")
try:
    db = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Notifications\wpndatabase.db")
    out.write(f"db exists: {os.path.exists(db)}\n")
    tmp = os.path.join(tempfile.gettempdir(), "vee_wpn_copy.db")
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(db + ext):
            shutil.copy2(db + ext, tmp + ext)
    con = sqlite3.connect(tmp)
    handlers = con.execute("SELECT RecordId, PrimaryId FROM NotificationHandler").fetchall()
    claude = [(r, p) for r, p in handlers if "claude" in (p or "").lower()]
    out.write(f"claude handlers: {claude}\n")
    for rid, pid in claude:
        rows = con.execute(
            "SELECT Id, ArrivalTime, Payload FROM Notification WHERE HandlerId=? ORDER BY Id DESC LIMIT 8",
            (rid,)).fetchall()
        out.write(f"\n== {pid}: {len(rows)} recent\n")
        for nid, at, payload in rows:
            text = payload.decode("utf-8", "ignore") if isinstance(payload, bytes) else str(payload)
            texts = re.findall(r"<text[^>]*>(.*?)</text>", text, re.S)
            out.write(f"{nid} {at} {texts}\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
