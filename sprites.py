"""Pixel sprites for the Vee mascot. 24 x 35 grid per frame."""

HEAD = [
    "........KKKKKKKK........",
    "......KKKKKKKKKKKK......",
    ".....KKKKKKHHKKKKKK.....",
    "....KKKKKKKHHKKKKKKK....",
    "....KKKKKSSSSSSKKKKK....",
    "...KKKKSSSSSSSSSSKKKK...",
    "...KKKSSSSSKSSSSSSKKK...",
    "...KKSSKKKSSSSKKKSSKK...",
    "...KKSSSWESSSSWESSSKK...",
    "...KKSSTEESSSSEETSSKK...",
    "...KKSPPSSSsSSSSPPSKK...",
    "...KKSSSSSSRRSSSSSSKK...",
    "...KKKSSSSLLLLSSSSKKK...",
    "...KKKKKSSSSSSSSKKKKK...",
]

PAL = {
    "K": "#1b1418", "H": "#3d2f36", "S": "#c98a62", "s": "#a96e4c", "E": "#1a1010",
    "W": "#ffffff", "P": "#e07a8a", "L": "#9c4a3c", "R": "#d9dde3", "T": "#2fb5a8",
    "D": "#22222a", "d": "#40404e", "w": "#e8e8e8", "M": "#b8697a", "m": "#8f4b5c",
    "O": "#111111", "j": "#7fa6cf", "J": "#5b83b0", "B": "#2f5fa8", "u": "#c9d6e0",
    "n": "#2a2d45", "f": "#e8d27a", "l": "#9fb3e0", "y": "#e6c35c", "i": "#eef1f8",
    "I": "#4a64a8", "x": "#5e6066", "e": "#8a8c93", "c": "#a9c4ea", "h": "#3b3b40",
    "p": "#3a1f1a", "r": "#6e1a35", "z": "#c4466e", "v": "#f7f5f0", "V": "#d9d5cc",
    "Q": "#b0243a", "A": "#EF9F27", "Z": "#D4537E", "G": "#7F77DD",
    "g": "#1c1d22", "q": "#3b3d46", "k": "#2a2b31", "a": "#5fd3e6",
}

COLS, ROWS, TOP = 24, 35, 4
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def R(g, c0, c1, r0, r1, f):
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            g[r][c] = f(c, r) if callable(f) else f


def torso(g, f):
    R(g, 8, 15, 15, 18, f)
    R(g, 9, 14, 19, 20, f)


def arms(g, f):
    R(g, 7, 7, 15, 20, f)
    R(g, 16, 16, 15, 20, f)
    g[21][7] = "S"
    g[21][16] = "S"


def legs(g, a, b):
    R(g, 9, 10, a, b, "S")
    R(g, 13, 14, a, b, "S")


def shoes(g, a, b, ch):
    R(g, 9, 10, a, b, ch)
    R(g, 13, 14, a, b, ch)


def monday(g):
    torso(g, "D"); arms(g, "D")
    for r in (16, 17):
        g[r][10] = "w"; g[r][13] = "w"
    g[18][7] = "w"
    R(g, 10, 13, 19, 20, "d")
    R(g, 8, 15, 21, 22, lambda c, r: "m" if (c + r) % 3 == 0 else "M")
    R(g, 7, 16, 23, 23, "m")
    legs(g, 24, 26); shoes(g, 27, 29, "O")


def tuesday(g):
    torso(g, lambda c, r: "D" if r <= 16 else ("J" if c in (10, 13) else "j"))
    g[15][11] = "s"; g[15][12] = "s"
    arms(g, "D"); g[20][7] = "B"; g[20][16] = "B"
    R(g, 8, 15, 21, 22, "D")
    legs(g, 23, 25); shoes(g, 26, 29, "u")


def wednesday(g):
    def fl(c, r):
        if (c * 3 + r * 5) % 7 == 0:
            return "f"
        return "l" if (c * 5 + r * 3) % 9 == 0 else "n"
    torso(g, fl)
    R(g, 8, 15, 15, 15, "S"); g[15][9] = "n"; g[15][14] = "n"
    arms(g, "S"); g[19][16] = "B"; g[20][16] = "B"
    g[14][11] = "O"; g[14][12] = "O"
    R(g, 8, 15, 21, 22, fl); R(g, 8, 10, 23, 23, fl); R(g, 13, 15, 23, 23, fl)
    legs(g, 24, 25); shoes(g, 26, 29, "u")
    R(g, 5, 18, 3, 3, "y")  # headband


def thursday(g):
    st = lambda c, r=0: "I" if c % 2 else "i"
    torso(g, st); R(g, 8, 15, 21, 22, st)
    R(g, 11, 12, 20, 22, lambda c, r: "x" if r >= 21 else st(c))
    arms(g, st)
    R(g, 8, 15, 23, 23, lambda c, r: "x" if c % 2 else "e")
    legs(g, 24, 25); shoes(g, 26, 26, "c"); shoes(g, 27, 28, "h"); shoes(g, 29, 29, "p")


def friday(g):
    sq = lambda c, r: "z" if (c * 7 + r * 3) % 5 == 0 else "r"
    torso(g, sq)
    R(g, 8, 15, 15, 15, "S"); g[15][9] = "r"; g[15][14] = "r"
    R(g, 9, 14, 21, 22, sq)
    arms(g, "S"); legs(g, 23, 27); shoes(g, 28, 29, "O")


def saturday(g):
    lc = lambda c, r: "d" if (c + r) % 2 else "D"
    R(g, 8, 15, 15, 17, lc)
    R(g, 8, 15, 18, 18, lambda c, r: "w" if c % 3 == 0 else "O")
    R(g, 9, 14, 19, 20, "S")
    arms(g, lc); g[14][11] = "D"; g[14][12] = "D"
    R(g, 8, 15, 21, 23, lambda c, r: "d" if c == 11 and r > 21 else "D")
    R(g, 8, 10, 24, 27, lambda c, r: "d" if c == 9 and r % 2 else "D")
    R(g, 13, 15, 24, 27, lambda c, r: "d" if c == 14 and r % 2 else "D")
    R(g, 8, 10, 28, 29, "v"); R(g, 13, 15, 28, 29, "v")


def sunday(g):
    R(g, 8, 15, 15, 15, "S"); R(g, 10, 13, 15, 15, "v")
    R(g, 8, 15, 16, 18, "v"); R(g, 9, 14, 19, 19, "v")
    R(g, 9, 14, 20, 20, "Q"); g[20][11] = "R"; g[20][12] = "R"
    arms(g, "S")
    fo = lambda c, r: "V" if c in (10, 14) and r > 22 else "v"
    R(g, 8, 15, 21, 22, fo); R(g, 7, 16, 23, 27, fo); R(g, 7, 16, 28, 28, "V")
    shoes(g, 29, 29, "Q"); R(g, 17, 18, 21, 22, "Q")


OUTFITS = [monday, tuesday, wednesday, thursday, friday, saturday, sunday]


def build(day):
    g = [list(row) for row in HEAD] + [["."] * COLS for _ in range(16)]
    R(g, 4, 19, 14, 14, "K")
    R(g, 4, 6, 15, 18, "K"); R(g, 17, 19, 15, 18, "K")
    R(g, 5, 6, 19, 20, "K"); R(g, 17, 18, 19, 20, "K")
    R(g, 8, 8, 19, 20, "K"); R(g, 15, 15, 19, 20, "K")
    g[14][11] = "s"; g[14][12] = "s"
    OUTFITS[day](g)
    return g


HEART = [".Z.Z.", "ZZZZZ", ".ZZZ.", "..Z.."]


def step_legs(g, phase):
    """Lift one foot (blank its lowest row) to fake a walking step."""
    cols = (9, 10) if phase == 0 else (13, 14)
    for c in cols:
        for r in range(len(g) - 1, -1, -1):
            if g[r][c] != ".":
                g[r][c] = "."
                break


LID_MAX = 7          # fully open lid height in pixels
LID_BOTTOM = 25      # lid sits on her lap
LID_C0, LID_C1 = 7, 16
BASE_ROW = 26


def draw_laptop(g, lid, t, typing):
    """Dark grey gaming laptop. lid = 0 (closed, hidden) .. LID_MAX (open)."""
    if lid <= 0:
        return
    # keyboard deck seen from the front
    for c in range(LID_C0 - 1, LID_C1 + 2):
        g[BASE_ROW][c] = "k"
    g[BASE_ROW][LID_C0 - 1] = "g"; g[BASE_ROW][LID_C1 + 1] = "g"
    # back of the lid, rising as it opens
    top = LID_BOTTOM - lid + 1
    for r in range(top, LID_BOTTOM + 1):
        for c in range(LID_C0, LID_C1 + 1):
            edge = r == top or c in (LID_C0, LID_C1)
            g[r][c] = "g" if edge else "q"
    if lid == LID_MAX:
        mid = (LID_C0 + LID_C1) // 2
        g[top + 3][mid] = "a"; g[top + 3][mid + 1] = "a"   # small status light
        if typing:   # hands tapping just above the lid, one lifts at a time
            ph = (t // 2) % 2
            for cols, up in (((9, 10), ph == 0), ((13, 14), ph == 1)):
                for c in cols:
                    g[top - 2 if up else top - 1][c] = "S"


def frame(day, state, t, walking=False, flip=False, lid=0):
    """Return a ROWS x COLS grid of palette keys ('.' = transparent).
    lid: laptop lid height 0..LID_MAX (0 = no laptop)."""
    F = _frame(day, state, t, walking, lid)
    if flip:
        F = [row[::-1] for row in F]
    return F


def _frame(day, state, t, walking, lid=0):
    g = build(day)
    draw_laptop(g, lid, t, typing=(state == "work"))
    if walking:
        step_legs(g, (t // 2) % 2)
    if (t % 28) < 2 or state == "done":
        for k in (8, 9, 14, 15):
            g[8][k] = "S"; g[9][k] = "E"
    if state == "work":
        for k in (8, 9, 14, 15):
            g[9][k] = "S"
    if state in ("done", "need"):
        g[12][10] = "S"; g[12][13] = "S"
    if state == "done":
        g[13][11] = "L"; g[13][12] = "L"

    if walking:
        bob = (t // 2) % 2
    else:
        bob = (t // 5) % 2 if state in ("idle", "done") else 0
    F = [["."] * COLS for _ in range(ROWS)]
    for ri, row in enumerate(g):
        F[ri + TOP + bob] = row[:]

    if state == "work":
        for k in range((t // 4) % 4):
            F[2][17 + k * 2] = "G"
    elif state == "need" and (t // 4) % 2 == 0:
        for r in (0, 1, 2, 4):
            F[r][19] = "A"
    elif state == "done":
        hy = (t // 5) % 2
        for ri, row in enumerate(HEART):
            for ci, ch in enumerate(row):
                if ch != ".":
                    F[ri + hy][17 + ci] = ch
    return F
