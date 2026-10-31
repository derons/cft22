"""Pipelined player: one HTTP round-trip per ply (send + state read batched)."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests

import chain
import engine as E
import policy
import vrf

WINS = 15
MAX_SCAN = int(os.environ.get("MAX_SCAN", "4"))
DEADLINE = time.time() + float(os.environ.get("BUDGET", "3000"))
FLY_WAIT = float(os.environ.get("FLY_WAIT", "0.45"))


def fmt(b):
    return "".join("%+d" % p for p in b.points) + "|b%s|o%s" % (b.bar, b.off)


def grab_flag(ch):
    for a in range(8):
        try:
            r = requests.get(ch.url + "/flag", timeout=30)
            print("FLAG_RESPONSE:", repr(r.text[:400]), flush=True)
            if "ctfcup{" in r.text:
                print("FLAG:", r.text.strip(), flush=True)
                return True
        except Exception as e:
            print("flag fetch error: %r" % (e,), flush=True)
        time.sleep(1.0)
    return False


def alive(ch):
    try:
        r = requests.get(ch.url + "/", timeout=20)
        return "Invalid token" not in r.text
    except Exception:
        return False


class Fast:
    def __init__(self, ch):
        self.ch = ch

    def _state_calls(self):
        S = chain.S
        keys = ["gameId", "turn", "ptm", "committed", "posted", "d1", "d2", "board", "streak", "tokens"]
        return [("eth_call", [{"to": chain.ADDR, "data": "0x" + S[k].hex()}, "latest"]) for k in keys]

    def move_and_read(self, froms, dies, gas=None):
        """One round trip: send our move, then read the state (anvil mines on send)."""
        ch = self.ch
        gas = gas or chain.MOVE_GAS
        if ch.nonce is None:
            ch.sync_nonce()
        data = chain.enc_move(froms, dies)
        tx = {"to": chain.ADDR, "data": data, "gas": gas, "chainId": chain.CHAIN_ID,
              "nonce": ch.nonce, "gasPrice": 10 ** 9, "value": 0}
        signed = ch.acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        calls = [("eth_sendRawTransaction", ["0x" + raw.hex()])] + self._state_calls()
        res = ch.batch(calls)
        send = res[0]
        if "error" in send:
            ch.sync_nonce()
            return None, send["error"]
        ch.nonce += 1
        return ch.state_from(res[1:]), send["result"]


def play_game(fast, pl, gid, out):
    ch = fast.ch
    st = ch.state()
    fails = 0
    while st["committed"]:
        if time.time() > DEADLINE:
            out.append("DEADLINE")
            return
        t = st["turn"]
        if st["ptm"]:
            if not st["posted"]:
                st = ch.state()
                continue
            d = (st["d1"], st["d2"])
            end = pl.our_move(st["board"], d, vrf.dice_for(gid, t + 1))
            path = [] if end is None else E.path_to(st["board"], d, end)
            froms, dies = [p[0] for p in path], [p[1] for p in path]
            out.append("T%-3d US  %s %s -> %s" % (t, d, fmt(st["board"]), list(zip(froms, dies))))
            nst, msg = fast.move_and_read(froms, dies)
            if nst is None:
                fails += 1
                out.append("  !! %s (retry %d)" % (msg, fails))
                if fails > 8 or not alive(ch):
                    return
                st = ch.state()
                continue
            fails = 0
            if end is not None and end.current_won():
                out.append("  -> all 15 off")
            st = nst
            if end is not None:
                # the fly moves next: sleep its typical reaction time once here
                time.sleep(FLY_WAIT)
                st = ch.state()
        else:
            t0 = time.time()
            while st["committed"] and st["turn"] == t:
                if time.time() - t0 > 90:
                    out.append("  !! fly timeout t=%d" % t)
                    return
                time.sleep(0.12)
                st = ch.state()
    st = ch.state()
    out.append("after game: gameId=%d streak=%d tokens=%d" % (st["gameId"], st["streak"], st["tokens"]))


def main():
    ch = chain.Chain()
    fast = Fast(ch)
    pl = policy.Player()
    print("PLAYER %s balance=%d" % (ch.addr, ch.balance()), flush=True)
    st = ch.state()
    print("STATE %s" % {k: (fmt(v) if k == "board" else v) for k, v in st.items()}, flush=True)
    if st["streak"] >= WINS:
        grab_flag(ch)
        return
    while time.time() < DEADLINE:
        try:
            st = ch.state()
        except Exception as e:
            print("state error %r" % (e,), flush=True)
            if not alive(ch):
                print("INSTANCE DEAD", flush=True)
                return
            time.sleep(2)
            continue
        if st["streak"] >= WINS:
            print("SOLVED streak=%d" % st["streak"], flush=True)
            grab_flag(ch)
            return
        if st["committed"]:
            gid = st["gameId"]
            print("RESUME %d turn %d" % (gid, st["turn"]), flush=True)
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
                ok, msg = ch.skip()
                print("  skip", ok, msg, flush=True)
            ok, msg = ch.commit()
            print("COMMIT %d -> %s %s" % (pick, ok, msg), flush=True)
            gid = pick
        out = []
        try:
            play_game(fast, pl, gid, out)
        except Exception as e:
            out.append("exc %r" % (e,))
        print("\n".join(out), flush=True)
        if not alive(ch):
            print("INSTANCE DEAD", flush=True)
            return


if __name__ == "__main__":
    main()
