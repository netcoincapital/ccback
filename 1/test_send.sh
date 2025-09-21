#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-https://coinceeper.com/api/send}"
CJ="${COOKIE_JAR:-./coin_jar.cookies}"

USER_ID="63ff3616-abb3-4d03-b8d6-51a3c5a6dc08"
SENDER="0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956"
RECIPIENT="0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9"
AMOUNT="0.001966103059546"

# ---------- PREPARE ----------
prep_payload=$(jq -n \
  --arg uid "$USER_ID" \
  --arg chain "Ethereum" \
  --arg sender "$SENDER" \
  --arg recipient "$RECIPIENT" \
  --arg amount "$AMOUNT" \
  '{UserId:$uid, blockchain:$chain, sender_address:$sender, recipient_address:$recipient, amount:$amount, smart_contract_address:""}')

echo ">>> PREPARE $API_BASE/prepare"
prep_resp=$(curl -sS -i -c "$CJ" -b "$CJ" -X POST "$API_BASE/prepare" \
  -H "Content-Type: application/json" -H "Accept: application/json" -d "$prep_payload")
echo "$prep_resp" | sed -n '1,20p'
prep_body=$(sed -n '/^\r\?$/,$p' <<< "$prep_resp" | tail -n +2)

txid=$(jq -r '.transaction_id // empty' <<< "$prep_body")
expires_at=$(jq -r '.expires_at // empty' <<< "$prep_body")
success=$(jq -r '.success // empty' <<< "$prep_body")
chain_norm=$(jq -r '.details.blockchain // empty' <<< "$prep_body")

[[ "$success" == "true" && -n "$txid" ]] || { echo "❌ prepare failed"; exit 1; }
echo "✅ txid=$txid expires_at=$expires_at blockchain_in_resp=$chain_norm"
sleep 1

# ---------- کاندیداهای مختلف confirm ----------
declare -a payloads

# 1) نمونهٔ داک (lowercase chain + UserId)
payloads+=("$(jq -n --arg uid "$USER_ID" --arg tx "$txid" '{UserId:$uid, transaction_id:$tx, blockchain:"ethereum"}')")
# 2) chain مثل prepare (Capitalized)
payloads+=("$(jq -n --arg uid "$USER_ID" --arg tx "$txid" '{UserId:$uid, transaction_id:$tx, blockchain:"Ethereum"}')")
# 3) UserID به‌جای UserId
payloads+=("$(jq -n --arg uid "$USER_ID" --arg tx "$txid" '{UserID:$uid, transaction_id:$tx, blockchain:"ethereum"}')")
# 4) transactionId به‌جای transaction_id
payloads+=("$(jq -n --arg uid "$USER_ID" --arg tx "$txid" '{UserId:$uid, transactionId:$tx, blockchain:"ethereum"}')")
# 5) افزودن فیلدهای تکمیلی (برخی بک‌اندها لازم دارند)
payloads+=("$(jq -n --arg uid "$USER_ID" --arg tx "$txid" --arg sender "$SENDER" --arg recipient "$RECIPIENT" --arg amount "$AMOUNT" '{UserId:$uid, transaction_id:$tx, blockchain:"ethereum", sender_address:$sender, recipient_address:$recipient, amount:$amount}')")
# 6) همه‌چیز lowercase
payloads+=("$(jq -n --arg uid "$USER_ID" --arg tx "$txid" '{userid:$uid, transaction_id:$tx, blockchain:"ethereum"}')")
# 7) همه‌چیز CamelCase
payloads+=("$(jq -n --arg uid "$USER_ID" --arg tx "$txid" '{UserId:$uid, transactionId:$tx, Blockchain:"ethereum"}')")

echo ">>> Trying CONFIRM variants on $API_BASE/confirm"
i=0
for p in "${payloads[@]}"; do
  i=$((i+1))
  echo "---- Variant #$i payload ----"
  echo "$p" | jq .
  resp=$(curl -sS -i -c "$CJ" -b "$CJ" -X POST "$API_BASE/confirm" \
    -H "Content-Type: application/json" -H "Accept: application/json" -d "$p")
  status=$(awk 'BEGIN{RS="\r\n\r\n"} NR==1{print; exit}' <<< "$resp" | awk '/HTTP/{print $2}')
  body=$(sed -n '/^\r\?$/,$p' <<< "$resp" | tail -n +2)
  echo "HTTP_STATUS=$status"
  echo "$body" | jq . || true

  ok=$(jq -r '.success // empty' <<< "$body")
  if [[ "$status" == "200" && "$ok" == "true" ]]; then
    echo "✅ SUCCESS on variant #$i"
    exit 0
  fi
done

echo "❌ All confirm variants failed."
echo "Hint: اگر هیچ‌کدام موفق نشد، احتمالاً بک‌اند confirm به یکی از این‌ها وابسته است: هدر اختصاصی (مثلاً Authorization/X-API-Key یا X-Request-Id)، یا binding به IP/UserAgent، یا نیاز به CSRF/nonce."
exit 2
