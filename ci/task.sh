echo "probe from runner: $(date -u)"
curl -sS -m 20 https://mvwhs9b5ieeclup6.instances.ctfcup.online/ | head -20
echo "--- chainId ---"
curl -sS -m 20 -X POST -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' https://mvwhs9b5ieeclup6.instances.ctfcup.online
echo
