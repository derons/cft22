"""Our (cheating) player: knows every future roll; 2-ply search over the fly's *actual* dice."""
import time
import engine as E
import net as N
import vrf


class Player:
    def __init__(self, net=None, engine_mod=E, verbose=False):
        self.engine = engine_mod
        self.net = net or N.Net()
        self.verbose = verbose
        self.stats = {"fly_calls": 0, "our_calls": 0, "t": 0.0}

    # --- exact model of the fly's own move choice (port of agent.rs::choose_2ply) ---
    def fly_move(self, board, dice):
        t = time.time()
        mv = N.choose_2ply(self.net, self.engine, board, dice)
        self.stats["fly_calls"] += 1
        self.stats["t"] += time.time() - t
        return mv  # None => forced pass

    # --- our move: adversarial 2-ply using the fly's real next roll ---
    def our_move(self, board, dice, fly_dice):
        ends = self.engine.legal_end_boards(board, dice)
        if not ends:
            return None
        for e in ends:
            if e.current_won():
                return e
        rows = []
        spans = []
        for e in ends:
            e_opp = e.flip()
            replies = self.engine.legal_end_boards(e_opp, fly_dice)
            start = len(rows)
            if not replies:
                rows.append(N.encode(e))  # fly passes: our position persists
            else:
                rows.extend(N.encode(oe.flip()) for oe in replies)
            spans.append((start, len(rows)))
        eqs = self.net.equities(rows)
        best, best_val = ends[0], -float("inf")
        for e, (s, t) in zip(ends, spans):
            v = min(eqs[s:t])
            if v > best_val:
                best_val, best = v, e
        self.stats["our_calls"] += 1
        return best


def simulate_game(pl, game_id, max_turns=400, log=None):
    """Play a whole game with known dice.  Returns (winner, path_list)."""
    board = E.Board.new_game()
    t = 0
    moves = []
    while t < max_turns:
        d = vrf.dice_for(game_id, t)
        if t % 2 == 0:
            nd = vrf.dice_for(game_id, t + 1) if t + 1 < max_turns else (1, 1)
            end = pl.our_move(board, d, nd)
            path = [] if end is None else E.path_to(board, d, end)
            if end is not None and end.current_won():
                moves.append((t, d, path, board, end))
                return "player", moves
        else:
            end = pl.fly_move(board, d)
            path = [] if end is None else E.path_to(board, d, end)
            if end is not None and end.current_won():
                moves.append((t, d, path, board, end))
                return "fly", moves
        if end is None:  # forced pass
            nb = board
        else:
            nb = end
        if log is not None:
            log.append((t, d, path, board, nb))
        moves.append((t, d, path, board, nb))
        board = nb.flip()
        t += 1
    return "draw", moves
