"""Read-only diagnosis: ask the chain why our move would revert (eth_call)."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chain, engine as E, policy, vrf

ch = chain.Chain()
pl = policy.Player()
st = ch.state()
gid, t = st["gameId"], st["turn"]
board, d = st["board"], (st["d1"], st["d2"])
print("gid=%d turn=%d ptm=%s posted=%s dice=%s" % (gid, t, st["ptm"], st["posted"], d))
print("board:", "".join("%+d" % p for p in board.points), board.bar, board.off)

def try_call(tag, froms, dies):
    data = chain.enc_move(froms, dies)
    r = ch.one("eth_call", [{"from": ch.addr, "to": chain.ADDR, "data": "0x" + data.hex()}, "latest"])
    print("%-22s froms=%s dies=%s -> %s" % (tag, froms, dies, json.dumps(r)[:300]))

ends = E.legal_end_boards_with_paths(board, d)
print("legal ends:", len(ends))
end = pl.our_move(board, d, vrf.dice_for(gid, t + 1))
path = E.path_to(board, d, end)
print("our chosen end:", "".join("%+d" % p for p in end.points) if end else None)
print("our path:", path)
try_call("ours", [p[0] for p in path], [p[1] for p in path])
for i, (e, p) in enumerate(ends[:5]):
    try_call("alt%d" % i, [x[0] for x in p], [x[1] for x in p])
# also try a trivially-illegal move to see the revert string format
try_call("garbage", [0], [d[0]])
