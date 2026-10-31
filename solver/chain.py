"""Fast batched JSON-RPC client for the Flygammon contract (remote anvil over HTTPS)."""
import json
import os
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from eth_account import Account
from eth_abi import encode as abi_encode
from eth_utils import keccak

import engine as E

CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ci", "config.json")
CFG = json.load(open(CFG_PATH)) if os.path.exists(CFG_PATH) else {}
RPC = CFG.get("rpc", "")
ADDR = CFG.get("addr", "")
PK = CFG.get("pk", "")
MOVE_GAS = int(os.environ.get("MOVE_GAS", "9000000"))
CHAIN_ID = 31337


def sel(sig):
    return keccak(text=sig)[:4]


S = {k: sel(v) for k, v in {
    "skip": "skip()", "commit": "commit()", "move": "playerMove(uint8[],uint8[])",
    "streak": "streak()", "committed": "committed()", "posted": "dicePosted()",
    "ptm": "playerToMove()", "board": "boardPacked()", "d1": "d1()", "d2": "d2()",
    "tokens": "tokens()", "gameId": "gameId()", "turn": "turn()", "solved": "isSolved()",
}.items()}


def unpack_board(key):
    pts = [((key >> (6 * i)) & 0x3F) for i in range(24)]
    pts = [v - 64 if v >= 32 else v for v in pts]
    b = 144
    return E.Board(tuple(pts), ((key >> b) & 0x1F, (key >> (b + 5)) & 0x1F),
                   ((key >> (b + 10)) & 0x1F, (key >> (b + 15)) & 0x1F))


def enc_move(froms, dies):
    return S["move"] + abi_encode(["uint8[]", "uint8[]"], [list(froms), list(dies)])


class Chain:
    def __init__(self, rpc=RPC):
        self.url = rpc
        self.s = self._session()
        self.acct = Account.from_key(PK)
        self.addr = self.acct.address
        self.nonce = None
        self.lat = []

    def _session(self):
        s = requests.Session()
        ad = HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.3,
                                           allowed_methods=None, status_forcelist=[502, 503, 504]))
        s.mount("https://", ad)
        s.headers.update({"Connection": "close"})
        return s

    def batch(self, calls, tries=8):
        payload = [{"jsonrpc": "2.0", "id": i, "method": m, "params": p}
                   for i, (m, p) in enumerate(calls)]
        last = None
        for a in range(tries):
            t0 = time.time()
            try:
                r = self.s.post(self.url, json=payload, timeout=30).json()
                self.lat.append(time.time() - t0)
                if isinstance(r, dict):
                    r = [r]
                out = [None] * len(calls)
                for item in r:
                    out[item["id"]] = item
                return out
            except Exception as e:  # ssl eof, timeouts, bad json
                last = e
                time.sleep(min(0.4 + 0.6 * a, 6.0))
                self.s = self._session()
        raise RuntimeError("rpc unavailable: %r" % (last,))

    def one(self, m, p):
        return self.batch([(m, p)])[0]

    # ---------------- state ----------------
    def state(self):
        keys = ["gameId", "turn", "ptm", "committed", "posted", "d1", "d2", "board", "streak", "tokens"]
        res = self.batch([("eth_call", [{"to": ADDR, "data": "0x" + S[k].hex()}, "latest"]) for k in keys])
        v = {k: int(r["result"], 16) for k, r in zip(keys, res)}
        return {
            "gameId": v["gameId"], "turn": v["turn"], "ptm": v["ptm"] == 1,
            "committed": v["committed"] == 1, "posted": v["posted"] == 1,
            "d1": v["d1"], "d2": v["d2"], "board": unpack_board(v["board"]),
            "streak": v["streak"], "tokens": v["tokens"],
        }

    def balance(self):
        return int(self.one("eth_getBalance", [self.addr, "latest"])["result"], 16)

    def sync_nonce(self):
        self.nonce = int(self.one("eth_getTransactionCount", [self.addr, "pending"])["result"], 16)
        return self.nonce

    def block_gas_limit(self):
        r = self.one("eth_getBlockByNumber", ["latest", False])
        return int(r["result"]["gasLimit"], 16)

    # ---------------- tx ----------------
    def _raw(self, data, gas):
        if self.nonce is None:
            self.sync_nonce()
        tx = {"to": ADDR, "data": data, "gas": gas, "chainId": CHAIN_ID,
              "nonce": self.nonce, "gasPrice": 10 ** 9, "value": 0}
        signed = self.acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        r = self.one("eth_sendRawTransaction", ["0x" + raw.hex()])
        if "error" in r:
            self.sync_nonce()
            tx["nonce"] = self.nonce
            signed = self.acct.sign_transaction(tx)
            raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
            r = self.one("eth_sendRawTransaction", ["0x" + raw.hex()])
            if "error" in r:
                return None, r["error"]
        self.nonce += 1
        return r["result"], None

    def estimate(self, data, sender=None):
        r = self.one("eth_estimateGas", [{"from": sender or self.addr, "to": ADDR, "data": "0x" + data.hex()}])
        if "error" in r:
            return None, r["error"]
        return int(r["result"], 16), None

    def wait_receipts(self, hashes, timeout=90):
        pending, out = list(hashes), {}
        t0 = time.time()
        while pending and time.time() - t0 < timeout:
            res = self.batch([("eth_getTransactionReceipt", [h]) for h in pending])
            still = []
            for h, r in zip(pending, res):
                if r.get("result"):
                    out[h] = int(r["result"]["status"], 16)
                else:
                    still.append(h)
            pending = still
            if pending:
                time.sleep(0.05)
        return out

    def exec_tx(self, data, gas_min=300000, tries=3, label=""):
        """Estimate gas, send, and confirm. Returns (ok, msg)."""
        est, err = self.estimate(data)
        gas = max(gas_min, int((est or 300000) * 1.6) + 100000) if est else gas_min
        for a in range(tries):
            h, serr = self._raw(data, gas)
            if h is None:
                time.sleep(0.3)
                continue
            rc = self.wait_receipts([h], timeout=90).get(h)
            if rc == 1:
                return True, "ok gas=%d" % gas
            if rc == 0:
                est2, e2 = self.estimate(data)
                if est2:
                    gas = max(gas, int(est2 * 2.0) + 200000)
                time.sleep(0.2)
                continue
            return False, "receipt timeout"
        return False, "failed %s" % (label,)

    def skip(self):
        return self.exec_tx(S["skip"], gas_min=300000, label="skip")

    def commit(self):
        return self.exec_tx(S["commit"], gas_min=300000, label="commit")

    def move_fast(self, froms, dies, gas=None):
        """Fire-and-confirm-later move: one round trip, gas fixed to avoid estimateGas."""
        gas = gas or MOVE_GAS
        data = enc_move(froms, dies)
        h, err = self._raw(data, gas)
        return (h is not None), (err or "sent")

    def move(self, froms, dies):
        return self.exec_tx(enc_move(froms, dies), gas_min=3000000, label="move")
