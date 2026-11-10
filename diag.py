import collections, traceback
out = open("diag.txt", "w", encoding="utf-8")
try:
    import uiautomation as auto
    for w in auto.GetRootControl().GetChildren():
        try:
            out.write(f"TOP | {w.ClassName} | {w.Name!r}\n")
        except Exception:
            pass
    for w in auto.GetRootControl().GetChildren():
        if "claude" in (w.Name or "").lower():
            out.write(f"\n== WINDOW {w.ClassName} {w.Name!r}\n")
            types = collections.Counter(); btns = []
            for c, d in auto.WalkControl(w, maxDepth=60):
                types[c.ControlTypeName] += 1
                if c.ControlTypeName == "ButtonControl" and c.Name:
                    btns.append(c.Name.strip())
            out.write(f"types: {dict(types)}\nbuttons: {sorted(set(btns))}\n")
except Exception:
    out.write(traceback.format_exc())
out.close()
