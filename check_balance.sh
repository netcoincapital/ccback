#!/bin/bash

echo "💰 Checking Wallet Balance"
echo "=========================="

ADDRESS="0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956"

echo "Address: $ADDRESS"
echo ""

# Method 1: Check via Etherscan API
echo "1️⃣ Checking via Etherscan API..."
ETHERSCAN_RESPONSE=$(curl -s "https://api.etherscan.io/api?module=account&action=balance&address=$ADDRESS&tag=latest&apikey=YourApiKeyToken")
echo "Etherscan Response: $ETHERSCAN_RESPONSE"

# Extract balance from etherscan (in wei)
WEI_BALANCE=$(echo "$ETHERSCAN_RESPONSE" | jq -r '.result // "0"' 2>/dev/null || echo "0")
if [ "$WEI_BALANCE" != "0" ] && [ "$WEI_BALANCE" != "null" ]; then
    # Convert wei to ETH (divide by 10^18)
    ETH_BALANCE=$(echo "scale=18; $WEI_BALANCE / 1000000000000000000" | bc -l 2>/dev/null || echo "calculation_error")
    echo "Balance: $ETH_BALANCE ETH ($WEI_BALANCE wei)"
else
    echo "Balance: Unable to fetch or 0 ETH"
fi

echo ""

# Method 2: Check via our API (if we have a balance endpoint)
echo "2️⃣ Checking via our API..."
BALANCE_RESPONSE=$(curl -s -X POST https://coinceeper.com/api/send/debug-wallet \
  -H "Content-Type: application/json" \
  -d "{\"address\": \"$ADDRESS\", \"blockchain\": \"ethereum\"}")

echo "Our API Response:"
echo "$BALANCE_RESPONSE" | jq . 2>/dev/null || echo "$BALANCE_RESPONSE"

echo ""
echo "🔍 Analysis:"
echo "============"
echo "If balance is 0 or very low, you need to:"
echo "1. Send some ETH to this address for gas fees"
echo "2. The minimum recommended balance is ~0.01 ETH"
echo "3. For testing, even 0.005 ETH should be sufficient"

echo ""
echo "💡 Suggested Actions:"
echo "===================="
echo "1. Check the balance on Etherscan: https://etherscan.io/address/$ADDRESS"
echo "2. If balance is 0, send some test ETH to this address"
echo "3. If balance exists but still getting error, check if it's a different network (testnet vs mainnet)"
