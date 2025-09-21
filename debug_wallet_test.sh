#!/bin/bash

echo "🔍 Testing wallet existence in database..."

# Test the debug-wallet endpoint
curl -s -X POST https://coinceeper.com/api/send/debug-wallet \
  -H "Content-Type: application/json" \
  -d '{
    "address": "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956",
    "blockchain": "ethereum"
  }' | jq .

echo ""
echo "This will show if:"
echo "1. The blockchain exists in database"
echo "2. The address exists in database" 
echo "3. The address has a private key stored"
echo "4. The private key can be decrypted"
