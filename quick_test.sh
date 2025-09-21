[root@www CC]# ps aux | grep mysql
root      424841  0.0  0.0   4916  3456 ?        S    14:28   0:00 /bin/sh /www/server/mysql/bin/mysqld_safe --defaults-file=/etc/my.cnf --datadir=/www/server/data --pid-file=/var/run/mysqld/mysqld.pid
mysql     425502  1.9 13.9 1578476 522684 ?      Sl   14:28   0:02 /www/server/mysql/bin/mysqld --defaults-file=/etc/my.cnf --basedir=/www/server/mysql --datadir=/www/server/data --plugin-dir=/www/server/mysql/lib/plugin --user=mysql --log-error=www.coinceeper.com.err --open-files-limit=65535 --pid-file=/var/run/mysqld/mysqld.pid --socket=/run/mysqld/mysqld.sock --port=3306
root      426454  0.0  0.0   3872  1920 pts/1    S+   14:30   0:00 grep --color=auto mysql
[root@www CC]# #!/bin/bash

echo "⚡ Quick Transaction Test"
echo "========================"

# Test with very small amount
echo "Testing with 0.0001 ETH..."

PREPARE_RESPONSE=$(curl -s -X POST https://coinceeper.com/api/send/prepare \
  -H "Content-Type: application/json" \
  -d '{
    "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
    "blockchain": "Ethereum",
    "sender_address": "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956",
    "recipient_address": "0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9",
    "amount": "0.0001",
    "smart_contract_address": ""
  }')

echo "PREPARE Response:"
echo "$PREPARE_RESPONSE" | jq . 2>/dev/null || echo "$PREPARE_RESPONSE"

TRANSACTION_ID=$(echo "$PREPARE_RESPONSE" | jq -r '.transaction_id // empty' 2>/dev/null)

if [ -n "$TRANSACTION_ID" ]; then
    echo ""
    echo "CONFIRM Response:"
    curl -s -X POST https://coinceeper.com/api/send/confirm \
      -H "Content-Type: application/json" \
      -d "{
        \"UserId\": \"63ff3616-abb3-4d03-b8d6-51a3c5a6dc08\",
        \"blockchain\": \"Ethereum\",
        \"transaction_id\": \"$TRANSACTION_ID\"
      }" | jq . 2>/dev/null || echo "JSON parse failed"
else
    echo "❌ No transaction ID from PREPARE"
fi
