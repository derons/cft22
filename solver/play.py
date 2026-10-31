"""Live driver. play: resume/commit and play games; watch: dump state."""
import json
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
DEADLINE = time.time() + float(os.environ.get("BUDGET", "1500"))
MOVE_GAS = int(os.environ.get("MOVE_GAS", "0")) or None


def fmt(b):
    return "".join("%+d" % p for p in b.points) + "|b%s|o%s" % (b.bar, b.off)


def play_live(ch, pl, gid, out):
    st = ch.state()
    fails = 0
    while st["committed"]:
        if time.time() > DEADLINE:
            out.append("DEADLINE mid-game")
            return
        t = st["turn"]
        if st["ptm"]:
            if not st["posted"]:
                time.sleep(0.05)
                st = ch.state()
                continue
            board, d = st["board"], (st["d1"], st["d2"])
            end = pl.our_move(board, d, vrf.dice_for(gid, t + 1))
            path = [] if end is None else E.path_to(board, d, end)
            froms, dies = [p[0] for p in path], [p[1] for p in path]
            out.append("T%-3d US  %s %s -> %s" % (t, d, fmt(board), list(zip(froms, dies))))
            ok, msg = ch.move(froms, dies)
            if not ok:
                fails += 1
                out.append("  !! move failed (%s) tries=%d" % (msg, fails))
                if fails > 6:
                    return
                time.sleep(0.5)
            else:
                fails = 0
                if end is not None and end.current_won():
                    out.append("  -> all 15 off")
            time.sleep(0.8)
            st = ch.state()
        else:
            t0 = time.time()
            while True:
                st = ch.state()
                if (not st["committed"]) or st["turn"] != t:
                    break
                if time.time() - t0 > 120:
                    out.append("  !! fly move timeout at %d" % t)
                    return
                time.sleep(0.15)
    st = ch.state()
    out.append("after game: gameId=%d streak=%d tokens=%d" % (st["gameId"], st["streak"], st["tokens"]))


def ensure_config():
    """(Re)run setup when ci/config.json is missing or points at another instance."""
    cfgp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ci", "config.json")
    want = os.environ.get("INSTANCE", "").rstrip("/")
    if os.path.exists(cfgp):
        cfg = json.load(open(cfgp))
        if not want or cfg.get("rpc", "") == want:
            return cfg
    if not want:
        raise SystemExit("no config and no INSTANCE url")
    import setup
    setup.main_url(want)
    return json.load(open(cfgp))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "watch"
    ensure_config()
    ch = chain.Chain()
    pl = policy.Player()
    t0 = time.time()
    for _ in range(3):
        ch.one("eth_blockNumber", [])
    print("latency: single=%.2fs" % ((time.time() - t0) / 3), flush=True)
    print("PLAYER %s balance=%d" % (ch.addr, ch.balance()), flush=True)
    st = ch.state()
    print("STATE %s" % {k: (fmt(v) if k == "board" else v) for k, v in st.items()}, flush=True)
    print("latency: state_batch=%.2fs" % ch.lat[-1], flush=True)
    if mode == "watch":
        return
    while time.time() < DEADLINE:
        try:
            st = ch.state()
        except Exception as e:
            print("state read failed: %r" % (e,), flush=True)
            time.sleep(2)
            continue
        if st["streak"] >= WINS:
            print("SOLVED streak=%d" % st["streak"], flush=True)
            return
        if st["tokens"] == 0:
            print("NO TOKENS", flush=True)
            return
        if st["committed"]:
            gid = st["gameId"]
            print("RESUME game %d turn %d" % (gid, st["turn"]), flush=True)
        else:
            gid = st["gameId"]
            pick = gid
            t1 = time.time()
            for k in range(MAX_SCAN):
                w, mv = policy.simulate_game(pl, gid + k)
                print("  sim %d -> %s (%d plies, %.0fs)" % (gid + k, w, len(mv), time.time() - t1), flush=True)
                if w == "player":
                    pick = gid + k
                    break
            while ch.state()["gameId"] < pick:
                if time.time() > DEADLINE:
                    return
                ok, msg = ch.skip()
                print("  skip ->", ok, msg, flush=True)
                if not ok:
                    break
            print("COMMIT game %d" % pick, flush=True)
            ok, msg = ch.commit()
            print("  commit ->", ok, msg, flush=True)
            if not ok:
                time.sleep(1)
                continue
            time.sleep(0.2)
            gid = pick
        out = []
        try:
            play_live(ch, pl, gid, out)
        except Exception as e:
            out.append("play_live exception: %r" % (e,))
        print("\n".join(out), flush=True)
        try:
            st = ch.state()
            print("RESULT gid=%d streak=%d tokens=%d" % (gid, st["streak"], st["tokens"]), flush=True)
        except Exception as e:
            print("state read failed after game: %r" % (e,), flush=True)
            time.sleep(2)


if __name__ == "__main__":
    main()
