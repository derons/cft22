import json, requests
from eth_utils import keccak

RPC = "https://mvwhs9b5ieeclup6.instances.ctfcup.online"
ADDR = "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"
_id = [0]
def rpc(method, params=None):
    _id[0] += 1
    r = requests.post(RPC, json={"jsonrpc":"2.0","id":_id[0],"method":method,"params":params or []}, timeout=25)
    try:
        return r.json()
    except Exception:
        return {"http": r.status_code, "text": r.text[:300]}

print("=== basic ===")
for m in ["web3_clientVersion","eth_chainId","net_version","eth_blockNumber","eth_accounts","eth_gasPrice","eth_maxPriorityFeePerGas","anvil_nodeInfo","hardhat_metadata"]:
    print(m, "->", json.dumps(rpc(m))[:400])

def sel(sig):
    return "0x" + keccak(text=sig)[:4].hex()

def call(sig, out=None):
    data = sel(sig)
    r = rpc("eth_call", [{"to": ADDR, "data": data}, "latest"])
    return r

print("=== contract reads ===")
reads = [
    ("P()","uint256"), ("G()","uint256"), ("H()","uint256"), ("N()","uint256"),
    ("tokens()","uint256"), ("streak()","uint256"), ("player()","address"), ("oracle()","address"),
    ("gameId()","uint256"), ("turn()","uint256"), ("playerToMove()","bool"), ("committed()","bool"),
    ("dicePosted()","bool"), ("d1()","uint8"), ("d2()","uint8"), ("boardPacked()","uint256"),
    ("isSolved()","bool"),
]
vals = {}
for sig, typ in reads:
    r = call(sig)
    v = r.get("result")
    if v and len(v) >= 66 and typ.startswith("uint"):
        vals[sig] = int(v, 16)
        print(f"{sig:16s} = {int(v,16)}")
    else:
        print(f"{sig:16s} -> {json.dumps(r)[:200]}")
    if sig in ("P()","G()","H()"):
        print("   hex:", (v or "")[:130])

print("=== code ===")
c = rpc("eth_getCode", [ADDR, "latest"])
code = c.get("result","")
print("code len bytes:", (len(code)-2)//2)
print("head:", code[:200])
print("=== storage slots 0..24 ===")
for i in range(0, 12):
    r = rpc("eth_getStorageAt", [ADDR, hex(i), "latest"])
    print(i, r.get("result"))

if "P()" in vals:
    P, G, Hh = vals["P()"], vals["G()"], vals["H()"]
    import sympy
    print("=== P analysis ===")
    print("P bits:", P.bit_length(), "isprime:", sympy.isprime(P))
    n = P - 1
    fac = sympy.factorint(n, limit=10**6)
    print("P-1 factorization (partial):", fac)
    print("unfactored remainder:", (n // sympy.prod([k**v for k,v in fac.items()])) if fac else n)
