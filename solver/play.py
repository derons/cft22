"""Live driver: select favourable games (we know all dice), commit, and play them out."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chain
import engine as E
import policy
import vrf

WINS_NEEDED = 15
MAX_SCAN = int(os.environ.get("MAX_SCAN", "8"))


def fmt(b):
    return "".join("%+d" % p for p in b.points) + "|bar%s|off%s" % (b.bar, b.off)


def play_one_live(ch, pl, gid, out, stats):
    """Play the committed game to completion. Returns 'player' or 'fly'."""
    seen_fly = set()
    while True:
        st = ch.state()
        if not st["committed"]:
            break
        t = st["turn"]
        if st["ptm"]:
            if not st["posted"]:
                time.sleep(0.1)
                continue
            board, d = st["board"], (st["d1"], st["d2"])
            fly_next = vrf.dice_for(gid, t + 1)
            end = pl.our_move(board, d, fly_next)
            path = [] if end is None else E.path_to(board, d, end)
            froms = [p[0] for p in path]
            dies = [p[1] for p in path]
            out.append("T%-3d US  dice=%s board=%s path=%s" % (t, d, fmt(board), list(zip(froms, dies))))
            r = ch.move(froms, dies)
            stats["moves"] += 1
            if end is not None and end.current_won():
                out.append("  -> WE BEARED OFF ALL 15")
                return "player"
        else:
            if t in seen_fly:
                time.sleep(0.1)
                continue
            seen_fly.add(t)
            board, d = st["board"], vrf.dice_for(gid, t)
            pred = pl.fly_move(board, d)
            pred_path = [] if pred is None else E.path_to(board, d, pred)
            out.append("T%-3d FLY dice=%s board=%s pred=%s" % (t, d, fmt(board), list(zip([p[0] for p in pred_path], [p[1] for p in pred_path]))))
            t0 = time.time()
            while True:
                st2 = ch.state()
                if (not st2["committed"]) or st2["turn"] != t:
                    break
                if time.time() - t0 > 120:
                    raise TimeoutError("fly move timeout at turn %d" % t)
                time.sleep(0.1)
            expect = board.flip() if pred is None else pred.flip()
            if not st2["committed"]:
                stats["fly_bad"] += 0  # game ended on the fly's move
                out.append("  -> game over by fly move (fly won)")
                return "fly"
            if st2["board"] == expect:
                stats["fly_ok"] += 1
            else:
                stats["fly_bad"] += 1
                out.append("  *** FLY MISMATCH *** actual=%s" % fmt(st2["board"]))
    st = ch.state()
    out.append("game over: gameId=%d streak=%d tokens=%d" % (st["gameId"], st["streak"], st["tokens"]))
    return None


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "test"
    max_games = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    ch = chain.Chain()
    pl = policy.Player()
    stats = {"fly_ok": 0, "fly_bad": 0, "moves": 0, "wins": 0}
    bal = ch.w3.eth.get_balance(ch.addr)
    st = ch.state()
    print("player=%s balance=%d gameId=%d streak=%d tokens=%d committed=%s"
          % (ch.addr, bal, st["gameId"], st["streak"], st["tokens"], st["committed"]), flush=True)
    if bal == 0:
        print("NO GAS - abort", flush=True)
        return
    for g in range(max_games):
        st = ch.state()
        if st["streak"] >= WINS_NEEDED:
            print("SOLVED already", flush=True)
            break
        if st["committed"]:
            gid = st["gameId"]
            print("resuming committed game %d" % gid, flush=True)
        else:
            gid = st["gameId"]
            pick = None
            if mode == "run":
                t0 = time.time()
                for k in range(MAX_SCAN):
                    cand = gid + k
                    w, mv = policy.simulate_game(pl, cand)
                    print("  sim gameId %d -> %s (%d plies, %.0fs)" % (cand, w, len(mv), time.time() - t0), flush=True)
                    if w == "player":
                        pick = cand
                        break
                if pick is None:
                    print("no winning game found in %d candidates; playing head" % MAX_SCAN, flush=True)
                    pick = gid
            else:
                pick = gid
            while ch.state()["gameId"] < pick:
                ch.skip()
            st = ch.state()
            print("committing game %d (tokens %d)" % (st["gameId"], st["tokens"]), flush=True)
            ch.commit()
            time.sleep(0.25)
        out = []
        res = play_one_live(ch, pl, gid, out, stats)
        print("\n".join(out), flush=True)
        st = ch.state()
        if st["streak"] > 0 and st["streak"] > (stats.get("last_streak", 0)):
            stats["wins"] += 1
        stats["last_streak"] = st["streak"]
        print("RESULT gid=%d res=%s streak=%d tokens=%d fly_pred ok=%d bad=%d"
              % (gid, res, st["streak"], st["tokens"], stats["fly_ok"], stats["fly_bad"]), flush=True)
        if st["tokens"] == 0:
            print("OUT OF TOKENS", flush=True)
            break


if __name__ == "__main__":
    main()
