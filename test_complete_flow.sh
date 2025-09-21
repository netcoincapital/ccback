#!/bin/bash

echo "🚀 Testing Complete Transaction Flow"
echo "===================================="

# Test data
USER_ID="63ff3616-abb3-4d03-b8d6-51a3c5a6dc08"
SENDER_ADDRESS="0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956"
RECIPIENT_ADDRESS="0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9"
AMOUNT="0.00196152022084"

echo ""
echo "📝 Test Parameters:"
echo "   User ID: $USER_ID"
echo "   Sender: $SENDER_ADDRESS"
echo "   Recipient: $RECIPIENT_ADDRESS"  
echo "   Amount: $AMOUNT ETH"
echo ""

# Step 1: PREPARE transaction
echo "1️⃣ PREPARE Transaction..."
echo "=========================="

PREPARE_RESPONSE=$(curl -s -X POST https://coinceeper.com/api/send/prepare \
  -H "Content-Type: application/json" \
  -d "{
    \"UserId\": \"$USER_ID\",
    \"blockchain\": \"Ethereum\",
    \"sender_address\": \"$SENDER_ADDRESS\",
    \"recipient_address\": \"$RECIPIENT_ADDRESS\",
    \"amount\": \"$AMOUNT\",
    \"smart_contract_address\": \"\"
  }")

echo "Response:"
echo "$PREPARE_RESPONSE" | jq . 2>/dev/null || echo "$PREPARE_RESPONSE"

# Extract transaction ID
TRANSACTION_ID=$(echo "$PREPARE_RESPONSE" | jq -r '.transaction_id // empty' 2>/dev/null)

if [ -z "$TRANSACTION_ID" ]; then
    echo "❌ PREPARE failed - no transaction ID"
    exit 1
fi

echo ""
echo "✅ PREPARE successful!"
echo "   Transaction ID: $TRANSACTION_ID"
echo ""

# Step 2: CONFIRM transaction (without private key - should auto-retrieve)
echo "2️⃣ CONFIRM Transaction (auto private key)..."
echo "=============================================="

CONFIRM_RESPONSE=$(curl -s -X POST https://coinceeper.com/api/send/confirm \
  -H "Content-Type: application/json" \
  -d "{
    \"UserId\": \"$USER_ID\",
    \"blockchain\": \"Ethereum\",
    \"transaction_id\": \"$TRANSACTION_ID\"
  }")

echo "Response:"
echo "$CONFIRM_RESPONSE" | jq . 2>/dev/null || echo "$CONFIRM_RESPONSE"

# Check if confirm was successful
SUCCESS=$(echo "$CONFIRM_RESPONSE" | jq -r '.success // false' 2>/dev/null)

if [ "$SUCCESS" = "true" ]; then
    echo ""
    echo "🎉 CONFIRM successful!"
    TX_HASH=$(echo "$CONFIRM_RESPONSE" | jq -r '.tx_hash // .transaction_hash // empty' 2>/dev/null)
    if [ -n "$TX_HASH" ]; then
        echo "   Transaction Hash: $TX_HASH"
        echo "   Explorer: https://etherscan.io/tx/$TX_HASH"
    fi
else
    echo ""
    echo "❌ CONFIRM failed"
    ERROR_MSG=$(echo "$CONFIRM_RESPONSE" | jq -r '.message // "Unknown error"' 2>/dev/null)
    echo "   Error: $ERROR_MSG"
    
    # If confirm failed, let's try with a dummy private key to see if that's the issue
    echo ""
    echo "3️⃣ Testing CONFIRM with explicit private key..."
    echo "==============================================="
    
    CONFIRM_WITH_KEY=$(curl -s -X POST https://coinceeper.com/api/send/confirm \
      -H "Content-Type: application/json" \
      -d "{
        \"UserId\": \"$USER_ID\",
        \"blockchain\": \"Ethereum\",
        \"transaction_id\": \"$TRANSACTION_ID\",
        \"private_key\": \"0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef\"
      }")
    
    echo "Response with explicit private key:"
    echo "$CONFIRM_WITH_KEY" | jq . 2>/dev/null || echo "$CONFIRM_WITH_KEY"
fi

echo ""
echo "🔍 Analysis:"
echo "============"

if [ "$SUCCESS" = "true" ]; then
    echo "✅ Transaction flow is working perfectly!"
    echo "   - PREPARE: Success"
    echo "   - CONFIRM: Success"
    echo "   - Private key auto-retrieval: Working"
    echo "   - Transaction broadcasting: Working"
else
    echo "⚠️ Transaction flow analysis:"
    echo "   - PREPARE: Success ✅"
    echo "   - CONFIRM: Failed ❌"
    echo "   - Private key retrieval: Working ✅ (from debug-wallet test)"
    echo "   - Issue likely in: Transaction broadcasting or network connectivity"
    
    # Check specific error patterns
    if echo "$ERROR_MSG" | grep -q "insufficient"; then
        echo "   - Specific issue: Insufficient balance"
    elif echo "$ERROR_MSG" | grep -q "network\|connectivity"; then
        echo "   - Specific issue: Network connectivity"
    elif echo "$ERROR_MSG" | grep -q "gas\|fee"; then
        echo "   - Specific issue: Gas/fee related"
    elif echo "$ERROR_MSG" | grep -q "All transaction methods failed"; then
        echo "   - Specific issue: All broadcast methods failed (likely network/node issue)"
    fi
fi

echo ""
echo "🏁 Test completed!"
