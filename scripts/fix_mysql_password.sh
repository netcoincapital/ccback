#!/bin/bash
# fix_mysql_password.sh — Sync MySQL password with .env file
set -e

ENV_FILE="/opt/coinceeper/CC/.env"

# Extract DB_PASSWORD from .env
DB_PASS=$(grep -oP 'DB_PASSWORD=\K.*' "$ENV_FILE" 2>/dev/null || echo "")

if [ -z "$DB_PASS" ]; then
  echo "ERROR: Could not read DB_PASSWORD from $ENV_FILE"
  exit 1
fi

echo "Updating MySQL password for coincee user..."
sudo mysql -e "ALTER USER 'coincee'@'localhost' IDENTIFIED BY '${DB_PASS}'; FLUSH PRIVILEGES;"
echo "MySQL password updated successfully"
