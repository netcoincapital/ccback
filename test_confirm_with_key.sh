#!/bin/bash

echo "Testing confirm with private key provided..."

# First prepare a transaction
echo ">>> PREPARE"
PREPARE_RESPONSE=$(curl -s -X POST https://coinceeper.com/api/send/prepare \
  -H "Content-Type: application/json" \
  -d '{
    "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
    "blockchain": "Ethereum",
    "sender_address": "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956",
    "recipient_address": "0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9",
    "amount": "0.002",
    "smart_contract_address": ""
  }')

echo "$PREPARE_RESPONSE" | jq .

# Extract transaction ID
TRANSACTION_ID=$(echo "$PREPARE_RESPONSE" | jq -r '.transaction_id // empty')

if [ -z "$TRANSACTION_ID" ]; then
    echo "❌ Failed to get transaction ID"
    exit 1
fi

echo "✅ Got transaction ID: $TRANSACTION_ID"

# Now test confirm WITH a private key
echo ">>> CONFIRM with private key"
curl -s -X POST https://coinceeper.com/api/send/confirm \
  -H "Content-Type: application/json" \
  -d "{
    \"UserId\": \"63ff3616-abb3-4d03-b8d6-51a3c5a6dc08\",
    \"blockchain\": \"Ethereum\",
    \"transaction_id\": \"$TRANSACTION_ID\",
    \"private_key\": \"0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef\"
  }" | jq .
