"""Minimal web3 client for the Flygammon contract (runs where the RPC is reachable)."""
import time
from eth_account import Account
from eth_utils import keccak
from web3 import Web3

import engine as E

RPC = "https://mvwhs9b5ieeclup6.instances.ctfcup.online"
ADDR = "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"
PK = "0xea72cf390e9d4410fde4d7ecbecf3cd60fde602bda76aff599c7275855d61468"


def sel(sig):
    return keccak(text=sig)[:4]


S_SKIP = sel("skip()")
S_COMMIT = sel("commit()")
S_MOVE = sel("playerMove(uint8[],uint8[])")
S_STREAK = sel("streak()")
S_COMMITTED = sel("committed()")
S_POSTED = sel("dicePosted()")
S_PTM = sel("playerToMove()")
S_BOARD = sel("boardPacked()")
S_D1 = sel("d1()")
S_D2 = sel("d2()")
S_TOKENS = sel("tokens()")
S_GID = sel("gameId()")
S_TURN = sel("turn()")
S_SOLVED = sel("isSolved()")


def unpack_board(key: int) -> E.Board:
    pts = []
    for i in range(24):
        v = (key >> (6 * i)) & 0x3F
        pts.append(v - 64 if v >= 32 else v)
    base = 144
    bar = ((key >> base) & 0x1F, (key >> (base + 5)) & 0x1F)
    off = ((key >> (base + 10)) & 0x1F, (key >> (base + 15)) & 0x1F)
    return E.Board(tuple(pts), bar, off)


def encode_move(froms, dies) -> bytes:
    from eth_abi import encode as abi_encode
    return S_MOVE + abi_encode(["uint8[]", "uint8[]"], [list(froms), list(dies)])


class Chain:
    def __init__(self, rpc=RPC):
        self.w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 25}))
        self.acct = Account.from_key(PK)
        self.addr = self.acct.address

    def read(self, selector) -> int:
        r = self.w3.eth.call({"to": ADDR, "data": selector})
        return int.from_bytes(r, "big")

    def state(self):
        st = {}
        st["gameId"] = self.read(S_GID)
        st["turn"] = self.read(S_TURN)
        st["ptm"] = self.read(S_PTM) == 1
        st["committed"] = self.read(S_COMMITTED) == 1
        st["posted"] = self.read(S_POSTED) == 1
        st["d1"] = self.read(S_D1)
        st["d2"] = self.read(S_D2)
        st["board"] = unpack_board(self.read(S_BOARD))
        st["streak"] = self.read(S_STREAK)
        st["tokens"] = self.read(S_TOKENS)
        return st

    def send(self, data: bytes, gas=900000):
        tx = {
            "to": ADDR, "data": data, "gas": gas, "chainId": self.w3.eth.chain_id,
            "nonce": self.w3.eth.get_transaction_count(self.addr, "pending"),
            "gasPrice": self.w3.eth.gas_price, "value": 0,
        }
        signed = self.acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        h = self.w3.eth.send_raw_transaction(raw)
        return self.w3.eth.wait_for_transaction_receipt(h, timeout=60)

    def skip(self):
        return self.send(S_SKIP, gas=400000)

    def commit(self):
        return self.send(S_COMMIT, gas=400000)

    def move(self, froms, dies):
        return self.send(encode_move(list(froms), list(dies)), gas=1500000)
