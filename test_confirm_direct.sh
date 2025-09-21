#!/bin/bash

echo "🔍 Direct Confirm Test"
echo "====================="

# Use the transaction ID from the last test
TRANSACTION_ID="9474290b-05dc-4a00-a71d-228111960e4b"

echo "Testing CONFIRM with transaction ID: $TRANSACTION_ID"

curl -X POST https://coinceeper.com/api/send/confirm \
  -H "Content-Type: application/json" \
  -d "{
    \"UserId\": \"63ff3616-abb3-4d03-b8d6-51a3c5a6dc08\",
    \"blockchain\": \"Ethereum\",
    \"transaction_id\": \"$TRANSACTION_ID\"
  }"

echo ""
echo "Raw response above - checking for JSON vs HTML"
