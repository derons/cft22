"""VRF prediction: we recovered the oracle secret s, so every (gameId, turn) roll is known."""
from Crypto.Hash import keccak

P = 69791413546914595802347733061036845443281698557187053530193101591522424466219
S = 50311264449498499212645012083343631218300571912059484696268200645472145571621


def _keccak(b: bytes) -> bytes:
    h = keccak.new(digest_bits=256)
    h.update(b)
    return h.digest()


def u_for(game_id: int, turn: int) -> int:
    u = int.from_bytes(_keccak(b"flygammon-vrf-u" + game_id.to_bytes(32, "big") + turn.to_bytes(32, "big")), "big") % P
    if u < 2:
        u += 2
    return u


def y_for(game_id: int, turn: int, s: int = S) -> int:
    return pow(u_for(game_id, turn), s, P)


def dice_from_y(y: int):
    hh = int.from_bytes(_keccak(b"flygammon-vrf-dice" + y.to_bytes(32, "big")), "big")
    return (hh % 6) + 1, ((hh >> 8) % 6) + 1


def dice_for(game_id: int, turn: int, s: int = S):
    return dice_from_y(y_for(game_id, turn, s))


if __name__ == "__main__":
    print("u(0,0) =", u_for(0, 0))
    print("y(0,0) =", y_for(0, 0))
    print("dice(0,0) =", dice_for(0, 0))
    print("dice(0,1) =", dice_for(0, 1))
