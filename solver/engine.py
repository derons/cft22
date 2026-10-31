"""Faithful Python port of model-src/engine.rs (Backgammon engine, mover's perspective)."""
from dataclasses import dataclass, replace

N_POINTS = 24
CUR, OPP = 0, 1
BAR_FROM = 24


@dataclass(frozen=True)
class Board:
    points: tuple  # 24 ints
    bar: tuple     # (cur, opp)
    off: tuple     # (cur, opp)

    @staticmethod
    def new_game():
        p = [0] * 24
        p[23] = 2; p[12] = 5; p[7] = 3; p[5] = 5
        p[0] = -2; p[11] = -5; p[16] = -3; p[18] = -5
        return Board(tuple(p), (0, 0), (0, 0))

    def flip(self):
        p = tuple(-self.points[N_POINTS - 1 - i] for i in range(N_POINTS))
        return Board(p, (self.bar[OPP], self.bar[CUR]), (self.off[OPP], self.off[CUR]))

    def all_current_home(self):
        if self.bar[CUR] > 0:
            return False
        return all(self.points[i] <= 0 for i in range(6, N_POINTS))

    def current_won(self):
        return self.off[CUR] == 15


def single_moves(b, d):
    """Legal single-checker moves for one die -> list of (Board, from_index or BAR_FROM)."""
    res = []
    if b.bar[CUR] > 0:
        t = N_POINTS - d
        if b.points[t] > -2:
            pts = list(b.points); bar = list(b.bar)
            if pts[t] == -1:
                pts[t] = 0; bar[OPP] += 1
            pts[t] += 1; bar[CUR] -= 1
            res.append((Board(tuple(pts), tuple(bar), b.off), BAR_FROM))
        return res
    all_home = b.all_current_home()
    for p in range(N_POINTS):
        if b.points[p] <= 0:
            continue
        target = p - d
        if target >= 0:
            if b.points[target] > -2:
                pts = list(b.points); bar = list(b.bar)
                if pts[target] == -1:
                    pts[target] = 0; bar[OPP] += 1
                pts[target] += 1; pts[p] -= 1
                res.append((Board(tuple(pts), tuple(bar), b.off), p))
        elif all_home:
            pip = p + 1
            if d == pip:
                pts = list(b.points); off = list(b.off)
                pts[p] -= 1; off[CUR] += 1
                res.append((Board(tuple(pts), b.bar, tuple(off)), p))
            elif d > pip:
                if not any(b.points[i] > 0 for i in range(p + 1, 6)):
                    pts = list(b.points); off = list(b.off)
                    pts[p] -= 1; off[CUR] += 1
                    res.append((Board(tuple(pts), b.bar, tuple(off)), p))
    return res


def apply_single(b, frm, d):
    for nb, f in single_moves(b, d):
        if f == frm:
            return sb_nb(nb)
    return None


def sb_nb(nb):
    return nb


def _dfs(board, dice, used, out):
    advanced = False
    for i in range(len(dice)):
        d = dice[i]
        rest = dice[:i] + dice[i + 1:]
        for nb, frm in single_moves(board, d):
            advanced = True
            used.append((frm, d))
            _dfs(nb, rest, used, out)
            used.pop()
    if not advanced:
        out.append((board, list(used)))


def legal_end_boards_with_paths(board, dice):
    multiset = [dice[0]] * 4 if dice[0] == dice[1] else [dice[0], dice[1]]
    leaves = []
    _dfs(board, multiset, [], leaves)
    if not leaves:
        return []
    max_len = max(len(p) for _, p in leaves)
    if max_len == 0:
        return []
    kept = [(b, p) for b, p in leaves if len(p) == max_len]
    if max_len == 1 and dice[0] != dice[1]:
        larger = max(dice)
        if any(p[0][1] == larger for _, p in kept):
            kept = [(b, p) for b, p in kept if p[0][1] == larger]
    seen = set(); out = []
    for b, p in kept:
        if b not in seen:
            seen.add(b); out.append((b, p))
    return out


def legal_end_boards(board, dice):
    return [b for b, _ in legal_end_boards_with_paths(board, dice)]


def path_to(board, dice, target):
    for b, p in legal_end_boards_with_paths(board, dice):
        if b == target:
            return p
    return None


def score_points(b):
    if b.off[OPP] > 0:
        return 1
    if b.bar[OPP] > 0 or any(b.points[i] < 0 for i in range(6)):
        return 3
    return 2
