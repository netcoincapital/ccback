#!/bin/bash
# Setup script for CoinCeeper Database Backup System
# اسکریپت نصب سیستم بک‌آپ خودکار

set -e

echo "=========================================="
echo "CoinCeeper Database Backup System Setup"
echo "نصب سیستم بک‌آپ خودکار پایگاه داده"
echo "=========================================="

# Check if running as root for system service installation
if [[ $EUID -eq 0 ]]; then
    echo "⚠️  Running as root - will install system service"
    INSTALL_SERVICE=true
else
    echo "ℹ️  Running as regular user - will setup for current user only"
    INSTALL_SERVICE=false
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo ""
echo "بررسی پیش‌نیازها..."

# Check Python 3
if ! command_exists python3; then
    echo "❌ Python 3 not found. Please install Python 3."
    exit 1
fi
echo "✅ Python 3: $(python3 --version)"

# Check pip
if ! command_exists pip3; then
    echo "❌ pip3 not found. Please install python3-pip."
    exit 1
fi
echo "✅ pip3 found"

# Check MySQL client
if ! command_exists mysql; then
    echo "❌ MySQL client not found. Please install mysql-client."
    exit 1
fi
echo "✅ MySQL client: $(mysql --version | head -1)"

# Check mysqldump
if ! command_exists mysqldump; then
    echo "❌ mysqldump not found. Please install mysql-client."
    exit 1
fi
echo "✅ mysqldump found"

# Install Python dependencies
echo ""
echo "نصب وابستگی‌های Python..."
pip3 install -r backup/requirements.txt
echo "✅ Python dependencies installed"

# Create directories
echo ""
echo "ایجاد پوشه‌ها..."
mkdir -p backups
mkdir -p Logs
chmod 755 backups
chmod 755 Logs
echo "✅ Directories created"

# Setup environment file
echo ""
echo "تنظیم فایل محیطی..."
if [ ! -f .env ]; then
    cp backup/.env.example .env
    echo "✅ .env file created from template"
    echo "⚠️  Please edit .env file with your database credentials"
else
    echo "ℹ️  .env file already exists, skipping"
fi

# Set permissions
chmod 600 .env
echo "✅ Environment file permissions set"

# Make scripts executable
chmod +x backup/database_backup.py
chmod +x backup/backup_scheduler.py
chmod +x backup/setup.sh
echo "✅ Scripts made executable"

# Test configuration
echo ""
echo "تست پیکربندی..."
if python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
required_vars = ['DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_NAME']
missing = [var for var in required_vars if not os.getenv(var)]
if missing:
    print(f'❌ Missing environment variables: {missing}')
    print('Please edit .env file with your database credentials')
    exit(1)
else:
    print('✅ Environment variables configured')
"; then
    # Test database connection
    echo "Testing database connection..."
    if python3 -c "
import sys
sys.path.append('.')
from backup.database_backup import DatabaseBackup
try:
    backup = DatabaseBackup()
    backup.validate_config()
    print('✅ Database connection test passed')
except Exception as e:
    print(f'❌ Database connection test failed: {e}')
    print('Please check your database credentials in .env file')
    exit(1)
"; then
        echo "✅ Configuration test passed"
    else
        echo "❌ Configuration test failed"
        exit 1
    fi
else
    echo "❌ Environment configuration incomplete"
    exit 1
fi

# Install system service (if root)
if [ "$INSTALL_SERVICE" = true ]; then
    echo ""
    echo "نصب سرویس سیستمی..."
    
    # Create systemd service
    python3 backup/backup_scheduler.py --create-service
    
    # Enable and start service
    systemctl daemon-reload
    systemctl enable coinceeper-backup
    systemctl start coinceeper-backup
    
    echo "✅ System service installed and started"
    echo "Check status with: systemctl status coinceeper-backup"
else
    echo ""
    echo "راهنمای راه‌اندازی:"
    echo ""
    echo "1. For systemd service (requires root):"
    echo "   sudo ./backup/setup.sh"
    echo ""
    echo "2. For cron job:"
    echo "   crontab -e"
    echo "   Add: 0 2 * * * cd $(pwd) && /usr/bin/python3 backup/database_backup.py"
    echo ""
    echo "3. For manual scheduler:"
    echo "   nohup python3 backup/backup_scheduler.py &"
fi

# Run initial backup test
echo ""
echo "اجرای تست بک‌آپ اولیه..."
if python3 backup/backup_scheduler.py --manual-backup; then
    echo "✅ Initial backup test successful"
    echo ""
    echo "Backup files created in: ./backups/"
    ls -la backups/ | tail -5
else
    echo "❌ Initial backup test failed"
    echo "Please check the logs in ./Logs/ directory"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ Setup completed successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Check backup files in ./backups/ directory"
echo "2. Review logs in ./Logs/ directory"
echo "3. Test email notifications (if configured)"
echo ""
echo "Useful commands:"
echo "- Manual backup: python3 backup/backup_scheduler.py --manual-backup"
echo "- Check status: python3 backup/backup_scheduler.py --status"
echo "- View logs: tail -f Logs/database_backup.log"
echo ""
echo "For support, check backup/README.md"


