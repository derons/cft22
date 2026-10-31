"""Fast batched JSON-RPC client for the Flygammon contract (remote anvil over HTTPS)."""
import json
import time

import requests
from eth_account import Account
from eth_abi import encode as abi_encode
from eth_utils import keccak

import engine as E

RPC = "https://mvwhs9b5ieeclup6.instances.ctfcup.online"
ADDR = "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"
PK = "0xea72cf390e9d4410fde4d7ecbecf3cd60fde602bda76aff599c7275855d61468"
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
        self.s = requests.Session()
        self.acct = Account.from_key(PK)
        self.addr = self.acct.address
        self.nonce = None
        self._id = 0
        self.lat = []

    # ---- raw json-rpc ----
    def batch(self, calls):
        payload = []
        for i, (m, p) in enumerate(calls):
            payload.append({"jsonrpc": "2.0", "id": i, "method": m, "params": p})
        t0 = time.time()
        r = self.s.post(self.url, json=payload, timeout=30).json()
        self.lat.append(time.time() - t0)
        if isinstance(r, dict):
            r = [r]
        out = [None] * len(calls)
        for item in r:
            out[item["id"]] = item
        return out

    def one(self, m, p):
        return self.batch([(m, p)])[0]

    def call_single(self, selector):
        r = self.one("eth_call", [{"to": ADDR, "data": "0x" + selector.hex()}, "latest"])
        return int(r["result"], 16)

    # ---- state ----
    def state(self):
        keys = ["gameId", "turn", "ptm", "committed", "posted", "d1", "d2", "board", "streak", "tokens"]
        calls = [("eth_call", [{"to": ADDR, "data": "0x" + S[k].hex()}, "latest"]) for k in keys]
        res = self.batch(calls)
        v = {}
        for k, r in zip(keys, res):
            v[k] = int(r["result"], 16)
        st = {
            "gameId": v["gameId"], "turn": v["turn"], "ptm": v["ptm"] == 1,
            "committed": v["committed"] == 1, "posted": v["posted"] == 1,
            "d1": v["d1"], "d2": v["d2"], "board": unpack_board(v["board"]),
            "streak": v["streak"], "tokens": v["tokens"],
        }
        return st

    def balance(self):
        r = self.one("eth_getBalance", [self.addr, "latest"])
        return int(r["result"], 16)

    def sync_nonce(self):
        r = self.one("eth_getTransactionCount", [self.addr, "pending"])
        self.nonce = int(r["result"], 16)
        return self.nonce

    # ---- tx ----
    def send(self, data, gas=900000):
        if self.nonce is None:
            self.sync_nonce()
        tx = {
            "to": ADDR, "data": data, "gas": gas, "chainId": CHAIN_ID,
            "nonce": self.nonce, "gasPrice": 10**9, "value": 0,
        }
        signed = self.acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        r = self.one("eth_sendRawTransaction", ["0x" + raw.hex()])
        if "error" in r:
            # nonce/sync problem: resync and retry once
            self.sync_nonce()
            tx["nonce"] = self.nonce
            signed = self.acct.sign_transaction(tx)
            raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
            r = self.one("eth_sendRawTransaction", ["0x" + raw.hex()])
            if "error" in r:
                raise RuntimeError("send failed: %s" % r["error"])
        self.nonce += 1
        return r["result"]

    def wait_receipts(self, hashes, timeout=60):
        """Poll several receipt hashes in one batch; returns dict hash->status."""
        pending = list(hashes)
        out = {}
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

    def skip(self):
        return self.send(S["skip"], gas=300000)

    def commit(self):
        return self.send(S["commit"], gas=300000)

    def move(self, froms, dies):
        return self.send(enc_move(froms, dies), gas=1200000)
