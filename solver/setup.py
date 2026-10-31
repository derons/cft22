"""Fetch instance page, read VRF params from chain, recover the oracle secret s, write ci/config.json."""
import json
import math
import os
import re
import sys
import time

import requests
import sympy

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "..", "ci", "config.json")


def bsgs(g, h, p, order):
    m = math.isqrt(order) + 1
    table = {}
    e = 1
    for j in range(m):
        table.setdefault(e, j)
        e = e * g % p
    factor = pow(pow(g, p - 2, p), m, p)
    gamma = h % p
    for i in range(m + 1):
        if gamma in table:
            return i * m + table[gamma]
        gamma = gamma * factor % p
    return None


def dlog(g, h, p):
    n = p - 1
    fac = sympy.factorint(n, limit=3 * 10 ** 6)
    assert all(v == 1 for v in fac.values()), "repeated factors: %s" % fac
    M = 1
    for q in fac:
        M *= q
    assert M == n, "unfactored remainder"
    x, mod = 0, 1
    for q in fac:
        gq = pow(g, n // q, p)
        hq = pow(h, n // q, p)
        xi = bsgs(gq, hq, p, q)
        if xi is None:
            raise RuntimeError("dlog failed for factor %d" % q)
        t = ((xi - x) % q) * pow(mod % q, -1, q) % q
        x = x + mod * t
        mod *= q
    return x % n


def main_url(url):
    import json as _j
    rpc = url.rstrip("/")
    page = requests.get(rpc + "/", timeout=30).text
    print(page[:400], flush=True)
    pk = re.search(r"player key\s*:\s*(0x[0-9a-fA-F]{64})", page).group(1)
    addr = re.search(r"challenge\s*:\s*(0x[0-9a-fA-F]{40})", page).group(1)
    print("pk=%s addr=%s" % (pk, addr), flush=True)

    def call(sig):
        r = requests.post(rpc, json={"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                                     "params": [{"to": addr, "data": "0x" + sig}, "latest"]}, timeout=30)
        return int(r.json()["result"], 16)

    from eth_utils import keccak
    sel = lambda s: keccak(text=s)[:4].hex()
    P = call(sel("P()")); G = call(sel("G()")); H = call(sel("H()"))
    N = call(sel("N()")); tokens = call(sel("tokens()"))
    print("P bits=%d G=%d H=%d N=%d tokens=%d" % (P.bit_length(), G, H, N, tokens), flush=True)
    t0 = time.time()
    s = dlog(G, H, P)
    ok = pow(G, s, P) == H
    print("s=%d  verify=%s  (%.1fs)" % (s, ok, time.time() - t0), flush=True)
    if not ok:
        raise SystemExit("DLP verification failed")
    os.makedirs(os.path.dirname(CFG), exist_ok=True)
    json.dump({"rpc": rpc, "addr": addr, "pk": pk, "P": P, "G": G, "H": H, "s": s, "N": N}, open(CFG, "w"))
    print("wrote", CFG, flush=True)


def main():
    main_url(sys.argv[1])


if __name__ == "__main__":
    main()
