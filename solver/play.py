"""Live driver. run: simulate-pick a winning game, commit, play it. watch: dump state."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chain
import engine as E
import policy
import vrf

WINS = 15
MAX_SCAN = int(os.environ.get("MAX_SCAN", "6"))
VERIFY = os.environ.get("VERIFY", "0") == "1"
DEADLINE = time.time() + float(os.environ.get("BUDGET", "1500"))


def fmt(b):
    return "".join("%+d" % p for p in b.points) + "|b%s|o%s" % (b.bar, b.off)


def play_live(ch, pl, gid, out, stats):
    """Play the committed game. Returns 'player'/'fly'/None(on error)."""
    st = ch.state()
    while st["committed"]:
        if time.time() > DEADLINE:
            out.append("DEADLINE hit mid-game")
            return None
        t = st["turn"]
        if st["ptm"]:
            if not st["posted"]:
                time.sleep(0.05)
                st = ch.state()
                continue
            board, d = st["board"], (st["d1"], st["d2"])
            end = pl.our_move(board, d, vrf.dice_for(gid, t + 1))
            path = [] if end is None else E.path_to(board, d, end)
            froms = [p[0] for p in path]
            dies = [p[1] for p in path]
            out.append("T%-3d US  %s %s -> %s" % (t, d, fmt(board), list(zip(froms, dies))))
            h = ch.move(froms, dies)
            rc = ch.wait_receipts([h], timeout=60).get(h, 0)
            stats["moves"] += 1
            if rc != 1:
                out.append("  !! our move tx FAILED (status=%s)" % rc)
                return None
            if end is not None and end.current_won():
                out.append("  -> all 15 off")
            st = ch.state()
        else:
            if VERIFY:
                pred = pl.fly_move(st["board"], vrf.dice_for(gid, t))
            t0 = time.time()
            while True:
                st = ch.state()
                if (not st["committed"]) or st["turn"] != t:
                    break
                if time.time() - t0 > 120:
                    out.append("  !! fly move timeout at turn %d" % t)
                    return None
                time.sleep(0.08)
    st = ch.state()
    out.append("after game: gameId=%d streak=%d tokens=%d" % (st["gameId"], st["streak"], st["tokens"]))
    return None


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "watch"
    ch = chain.Chain()
    pl = policy.Player()
    stats = {"moves": 0}
    print("PLAYER %s balance=%d" % (ch.addr, ch.balance()), flush=True)
    st = ch.state()
    print("STATE %s" % {k: (fmt(v) if k == "board" else v) for k, v in st.items()}, flush=True)
    if mode == "watch":
        print("rpc latency samples:", ["%.2f" % x for x in ch.lat], flush=True)
        return
    games = 0
    while time.time() < DEADLINE:
        st = ch.state()
        if st["streak"] >= WINS:
            print("SOLVED streak=%d" % st["streak"], flush=True)
            return
        if st["tokens"] == 0:
            print("NO TOKENS", flush=True)
            return
        if st["committed"]:
            gid = st["gameId"]
            print("resume committed game %d turn %d" % (gid, st["turn"]), flush=True)
        else:
            gid = st["gameId"]
            pick = gid
            t0 = time.time()
            for k in range(MAX_SCAN):
                w, mv = policy.simulate_game(pl, gid + k)
                print("  sim %d -> %s (%d plies, %.0fs)" % (gid + k, w, len(mv), time.time() - t0), flush=True)
                if w == "player":
                    pick = gid + k
                    break
            while ch.state()["gameId"] < pick:
                if time.time() > DEADLINE:
                    return
                ch.skip()
            print("commit game %d (skip %d)" % (pick, pick - gid), flush=True)
            ch.commit()
            time.sleep(0.15)
            gid = pick
        out = []
        play_live(ch, pl, gid, out, stats)
        games += 1
        print("\n".join(out), flush=True)
        st = ch.state()
        print("RESULT gid=%d streak=%d tokens=%d moves=%d" % (gid, st["streak"], st["tokens"], stats["moves"]), flush=True)


if __name__ == "__main__":
    main()
