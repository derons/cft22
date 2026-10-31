#!/usr/bin/env python3
"""
Flygammon VRF break (ctfcup 2026).

The challenge contract implements a Chaum-Pedersen VRF over Z_p^*.  The group
parameters p, g, h are public (immutable contract fields).  The oracle secret is
s = log_g(h) mod p, and every dice roll for ply (gameId, turn) is derived from
y = u^s mod p.

The prime p was generated so that p-1 is *fully smooth*:

    p-1 = 2 * 558937 * 617857 * 1042901 * 751823 * 870169 * 877321 * 501637
             * 798131 * 897263 * 989743 * 762389 * 783829 * 677827

so the discrete log falls to Pohlig-Hellman + BSGS and is recovered in
milliseconds.  With s we can predict every roll of every future game, and since
skip() is free we can hand-pick a gameId whose dice sequence is favourable.

Usage:
    pip install eth-hash[pycryptodome]
    python dlp.py                # recover s, verify, print a few rolls
    python dlp.py 17 0 17 20     # print dice for (gameId, turn) pairs
"""
import sys
from hashlib import sha256
from math import gcd, isqrt
from random import randrange

from eth_hash.auto import keccak

# ---- live deployment parameters (read from the contract) -------------------
P = 59542135019038253973229890950380403852748593264440878510381149952935803452287
G = 5
H = 33000356474693902489206072769680218785232483244014366506670537756187581196069
N_DICE = 15  # contract N (wins in a row)


# ---- integer factorisation (Miller-Rabin + Pollard rho) --------------------
def is_prime(n: int) -> bool:
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for a in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def pollard_rho(n: int) -> int:
    if n % 2 == 0:
        return 2
    while True:
        c, x, y, d = randrange(1, n), randrange(0, n), 0, 1
        y = x
        while d == 1:
            x = (x * x + c) % n
            y = (y * y + c) % n
            y = (y * y + c) % n
            d = gcd(abs(x - y), n)
        if d != n:
            return d


def factor(n: int) -> dict:
    out = {}

    def rec(m: int):
        if m == 1:
            return
        if is_prime(m):
            out[m] = out.get(m, 0) + 1
            return
        d = pollard_rho(m)
        rec(d)
        rec(m // d)

    rec(n)
    return out


# ---- Pohlig-Hellman --------------------------------------------------------
def bsgs(g: int, h: int, p: int, order: int) -> int:
    m = isqrt(order) + 1
    table = {}
    e = 1
    for j in range(m):
        table.setdefault(e, j)
        e = e * g % p
    factor_inv = pow(g, -m, p)
    y = h
    for i in range(m):
        if y in table:
            return i * m + table[y]
        y = y * factor_inv % p
    raise ValueError("no discrete log")


def crt(pairs):
    x, mod = 0, 1
    for r, m in pairs:
        t = ((r - x) * pow(mod, -1, m)) % m
        x += mod * t
        mod *= m
        x %= mod
    return x, mod


def recover_secret(p: int = P, g: int = G, h: int = H) -> int:
    n = p - 1
    residues = []
    for q, e in factor(n).items():
        qe = q**e
        # project into the subgroup of order q^e
        gi = pow(g, n // qe, p)
        hi = pow(h, n // qe, p)
        gamma = pow(g, n // q, p)  # element of order q
        x = 0
        for k in range(e):
            cur = pow(hi * pow(gi, -x, p) % p, q ** (e - 1 - k), p)
            digit = bsgs(gamma, cur, p, q)
            x += digit * q**k
        residues.append((x, qe))
    s, mod = crt(residues)
    assert mod == n and pow(g, s, p) == h, "DLP failed"
    return s


# ---- VRF (mirrors VRF.sol) -------------------------------------------------
def u_for(game_id: int, turn: int, p: int = P) -> int:
    d = keccak(b"flygammon-vrf-u" + game_id.to_bytes(32, "big") + turn.to_bytes(32, "big"))
    u = int.from_bytes(d, "big") % p
    return u if u >= 2 else u + 2


def dice_from_y(y: int):
    hh = int.from_bytes(keccak(b"flygammon-vrf-dice" + y.to_bytes(32, "big")), "big")
    return hh % 6 + 1, (hh >> 8) % 6 + 1


def predict(game_id: int, turn: int, s: int):
    y = pow(u_for(game_id, turn), s, P)
    d1, d2 = dice_from_y(y)
    return y, d1, d2


def prove(game_id: int, turn: int, s: int):
    """A valid (y, a1, a2, z) proof, exactly as the oracle daemon builds it."""
    u = u_for(game_id, turn)
    y = pow(u, s, P)
    order = P - 1
    k = randrange(2, order)
    a1, a2 = pow(G, k, P), pow(u, k, P)
    c = int.from_bytes(keccak(
        b"".join(x.to_bytes(32, "big") for x in (P, G, H, u, y, a1, a2))), "big")
    z = (k + c * s) % order
    return y, a1, a2, z


def main() -> None:
    s = recover_secret()
    print(f"oracle secret s = {s}")
    print(f"check g^s == h: {pow(G, s, P) == H}")
    if len(sys.argv) >= 3:
        args = [int(x) for x in sys.argv[1:]]
        for i in range(0, len(args) - 1, 2):
            gid, turn = args[i], args[i + 1]
            y, d1, d2 = predict(gid, turn, s)
            print(f"game {gid} turn {turn}: dice {d1}-{d2}  y=0x{y:064x}")
        return
    print("\nfirst player rolls (turn 0,2,4,...) and fly rolls (1,3,5,...) for gameId 17:")
    for turn in range(8):
        _, d1, d2 = predict(17, turn, s)
        print(f"  turn {turn}: {d1}-{d2}")


if __name__ == "__main__":
    main()
