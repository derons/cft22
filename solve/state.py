import json, sys
from web3 import Web3

RPC = "https://nvamznjvudkbl886.instances.ctfcup.online"
ADDR = Web3.to_checksum_address("0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0")
PLAYER_KEY = "0xeb42a7eeedd173829fac19a214c97d37b0b0cdd8dd0a51a50ddb7429478f20fb"

ABI = json.loads("""[
 {"name":"player","outputs":[{"type":"address"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"oracle","outputs":[{"type":"address"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"N","outputs":[{"type":"uint256"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"tokens","outputs":[{"type":"uint256"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"streak","outputs":[{"type":"uint256"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"gameId","outputs":[{"type":"uint256"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"turn","outputs":[{"type":"uint256"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"playerToMove","outputs":[{"type":"bool"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"committed","outputs":[{"type":"bool"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"dicePosted","outputs":[{"type":"bool"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"d1","outputs":[{"type":"uint8"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"d2","outputs":[{"type":"uint8"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"P","outputs":[{"type":"uint256"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"G","outputs":[{"type":"uint256"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"H","outputs":[{"type":"uint256"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"isSolved","outputs":[{"type":"bool"}],"inputs":[],"stateMutability":"view","type":"function"},
 {"name":"boardInts","outputs":[{"type":"int256[28]"}],"inputs":[],"stateMutability":"view","type":"function"}
]""")

w3 = Web3(Web3.HTTPProvider(RPC, request_kwargs={"timeout": 30}))
print("connected:", w3.is_connected(), "chainId:", w3.eth.chain_id, "block:", w3.eth.block_number)
print("player addr:", Web3().eth.account.from_key(PLAYER_KEY).address)
c = w3.eth.contract(address=ADDR, abi=ABI)
for name in ["player", "oracle", "N", "tokens", "streak", "gameId", "turn", "playerToMove",
             "committed", "dicePosted", "d1", "d2", "P", "G", "H", "isSolved"]:
    try:
        print(name, "=", c.functions[name]().call())
    except Exception as e:
        print(name, "ERR", e)
try:
    print("board:", c.functions.boardInts().call())
except Exception as e:
    print("board ERR", e)
print("code size:", len(w3.eth.get_code(ADDR)))
print("player balance:", w3.eth.get_balance(Web3().eth.account.from_key(PLAYER_KEY).address))
