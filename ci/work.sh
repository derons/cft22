#!/usr/bin/env bash
RPC=https://mvwhs9b5ieeclup6.instances.ctfcup.online
ADDR=0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0
PLAYER=0xf0166D0b759c7E14b0998dc74B5be64e2d9722C3
call() { curl -sS -m 15 -X POST -H 'Content-Type: application/json' --data "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"$1\",\"params\":$2}" "$RPC"; echo; }
echo "== block =="; call eth_blockNumber '[]'
echo "== balance =="; call eth_getBalance "[\"$PLAYER\",\"latest\"]"
echo "== nonce =="; call eth_getTransactionCount "[\"$PLAYER\",\"latest\"]"
echo "== reads =="
for pair in "gameId:d7c81b55" "turn:8b299903" "playerToMove:2ee25c51" "committed:9b6b9664" "dicePosted:3b8c9faa" "d1:8c18f2f1" "d2:7ef1dbea" "boardPacked:dc853352" "streak:b3ab4f70" "tokens:9d63848a" "isSolved:64d98f6e"; do
  n="${pair%%:*}"; s="${pair##*:}"
  printf "%-14s " "$n"; call eth_call "[{\"to\":\"$ADDR\",\"data\":\"0x$s\"},\"latest\"]"
done
