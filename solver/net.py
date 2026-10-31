"""Exact numpy port of model-src (features + FlyNet) and the fly's move policies."""
import os
import numpy as np

N_INPUT = 203
N_OUTPUT = 5
N_POINTS = 24
CUR, OPP = 0, 1
HIDDEN = 80

_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model.fly")


class Net:
    def __init__(self, path=_MODEL_PATH):
        d = np.frombuffer(open(path, "rb").read(), dtype="<f4")
        off = 0

        def take(n):
            nonlocal off
            a = d[off:off + n].copy()
            off += n
            return a

        # burn Linear weight is [d_input, d_output]
        self.W1 = take(N_INPUT * HIDDEN).reshape(N_INPUT, HIDDEN).astype(np.float32)
        self.B1 = take(HIDDEN).astype(np.float32)
        self.W2 = take(HIDDEN * HIDDEN).reshape(HIDDEN, HIDDEN).astype(np.float32)
        self.B2 = take(HIDDEN).astype(np.float32)
        self.W3 = take(HIDDEN * N_OUTPUT).reshape(HIDDEN, N_OUTPUT).astype(np.float32)
        self.B3 = take(N_OUTPUT).astype(np.float32)
        assert off == len(d)

    def forward(self, x):
        h = np.maximum(x @ self.W1 + self.B1, 0.0)
        h = np.maximum(h @ self.W2 + self.B2, 0.0)
        o = h @ self.W3 + self.B3
        return (1.0 / (1.0 + np.exp(-o))).astype(np.float32)

    def equities(self, rows):
        if not rows:
            return []
        x = np.asarray(rows, dtype=np.float32)
        out = self.forward(x)
        return [float(2.0 * r[0] - 1.0 + r[1] + r[2] - r[3] - r[4]) for r in out]


def encode(b):
    v = np.zeros(N_INPUT, dtype=np.float32)
    for i in range(N_POINTS):
        c = b.points[i]
        if c == 0:
            continue
        base = i * 8 + (0 if c > 0 else 4)
        n = abs(c)
        v[base] = 1.0
        if n >= 2:
            v[base + 1] = 1.0
        if n >= 3:
            v[base + 2] = 1.0
        if n > 3:
            v[base + 3] = (n - 3) / 2.0
    g = N_POINTS * 8
    v[g] = b.bar[CUR] / 2.0
    v[g + 1] = b.bar[OPP] / 2.0
    v[g + 2] = b.off[CUR] / 15.0
    v[g + 3] = b.off[OPP] / 15.0
    pip_own = b.bar[CUR] * 25
    pip_opp = b.bar[OPP] * 25
    home_own = home_opp = blots_own = blots_opp = 0
    for i in range(N_POINTS):
        c = b.points[i]
        if c > 0:
            pip_own += c * (i + 1)
            if i < 6 and c >= 2:
                home_own += 1
            if c == 1:
                blots_own += 1
        elif c < 0:
            pip_opp += (-c) * (N_POINTS - i)
            if i >= 18 and c <= -2:
                home_opp += 1
            if c == -1:
                blots_opp += 1
    e = g + 4
    v[e] = pip_own / 167.0
    v[e + 1] = pip_opp / 167.0
    v[e + 2] = (pip_opp - pip_own) / 167.0
    v[e + 3] = home_own / 6.0
    v[e + 4] = home_opp / 6.0
    v[e + 5] = blots_own / 15.0
    v[e + 6] = blots_opp / 15.0
    return v


def dice_combos():
    out = []
    for a in range(1, 7):
        for b in range(a, 7):
            out.append(((a, b), 1.0 / 36.0 if a == b else 2.0 / 36.0))
    return out


TWO_PLY_CANDIDATES = 8


def choose_2ply(net, engine, board, dice):
    """Exact port of agent.rs::choose_2ply -> (end_board, path) or None for a forced pass."""
    ends = engine.legal_end_boards(board, dice)
    if not ends:
        return None
    for e in ends:
        if e.current_won():
            return e
    rows = [encode(e.flip()) for e in ends]
    opp_eq1 = net.equities(rows)
    order = sorted(range(len(ends)), key=lambda i: (opp_eq1[i], i))
    k = min(TWO_PLY_CANDIDATES, len(ends))
    shortlist = order[:k]
    combos = dice_combos()

    flat = []
    npos = 0
    cands = []
    for ei in shortlist:
        e = ends[ei]
        base_idx = npos
        flat.append(encode(e))
        npos += 1
        e_opp = e.flip()
        spans = []
        for d, w in combos:
            opp_ends = engine.legal_end_boards(e_opp, d)
            start = npos
            for oe in opp_ends:
                flat.append(encode(oe.flip()))
                npos += 1
            spans.append((w, start, npos))
        cands.append((ei, base_idx, spans))

    eqs = net.equities(flat)
    best = shortlist[0]
    best_val = -float("inf")
    for ei, base_idx, spans in cands:
        base = eqs[base_idx]
        val = 0.0
        for w, start, end in spans:
            vd = base if start == end else min(eqs[start:end])
            val += w * vd
        if val > best_val:
            best_val = val
            best = ei
    return ends[best]
