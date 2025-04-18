#!/usr/bin/env python3
"""
ابزار راه‌اندازی محیط اجرایی برای CoinCeeper
این اسکریپت محیط را بررسی کرده و مشکلات احتمالی را گزارش می‌دهد
"""

import os
import sys
import importlib
import subprocess
from pathlib import Path

def check_python_version():
    """بررسی نسخه پایتون"""
    print(f"Python version: {sys.version}")
    if sys.version_info < (3, 7):
        print("WARNING: Python version is too old. Minimum recommended version is 3.7")
        return False
    return True

def check_dependencies():
    """بررسی نصب بودن کتابخانه‌های مورد نیاز"""
    required_packages = [
        'flask', 'sqlalchemy', 'pika', 'flask_cors', 'flask_wtf', 
        'flask_openapi3', 'pydantic', 'bip_utils', 'pycryptodome'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"✓ {package} is installed")
        except ImportError:
            missing_packages.append(package)
            print(f"✗ {package} is NOT installed")
    
    if missing_packages:
        print("\nMissing packages detected. Install them with the following command:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_env_file():
    """بررسی فایل محیطی .env"""
    env_path = Path('.env')
    
    if not env_path.exists():
        print("✗ .env file not found!")
        return False
    
    env_variables = {
        'DATABASE_URL': False,
        'AES_SECRET_KEY': False,
        'FLASK_ENV': False,
        'SECRET_KEY': False
    }
    
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                for var in env_variables:
                    if line.startswith(f"{var}="):
                        env_variables[var] = True
    
    missing_vars = [var for var, exists in env_variables.items() if not exists]
    
    if missing_vars:
        print(f"✗ Missing environment variables in .env file: {', '.join(missing_vars)}")
        return False
    
    print("✓ .env file exists and contains required variables")
    return True

def check_database():
    """بررسی اتصال به پایگاه داده"""
    try:
        # بارگذاری متغیرهای محیطی از .env
        from dotenv import load_dotenv
        load_dotenv()
        
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            print("✗ DATABASE_URL environment variable is not set")
            return False
        
        if database_url.startswith('sqlite'):
            db_path = database_url.replace('sqlite:///', '')
            if os.path.exists(db_path):
                print(f"✓ SQLite database file exists at {db_path}")
            else:
                print(f"✗ SQLite database file does not exist at {db_path}")
                print("  It will be created on first run")
        
        elif database_url.startswith(('mysql', 'postgresql')):
            # تلاش برای اتصال به دیتابیس
            try:
                if 'mysql' in database_url:
                    import mysql.connector
                    parts = database_url.replace('mysql+mysqlconnector://', '').split('/')
                    db_name = parts[1].split('?')[0]
                    user_pass_host = parts[0].split('@')
                    host = user_pass_host[1] if len(user_pass_host) > 1 else 'localhost'
                    user_pass = user_pass_host[0].split(':')
                    user = user_pass[0]
                    password = user_pass[1] if len(user_pass) > 1 else ''
                    
                    print(f"Trying to connect to MySQL database {db_name} at {host} as {user}")
                    conn = mysql.connector.connect(
                        user=user,
                        password=password,
                        host=host,
                        database=db_name
                    )
                    if conn.is_connected():
                        print(f"✓ Successfully connected to MySQL database {db_name}")
                        conn.close()
                    else:
                        print(f"✗ Failed to connect to MySQL database {db_name}")
                else:
                    print("✗ Non-MySQL databases not fully supported by this script")
            except Exception as e:
                print(f"✗ Failed to connect to database: {str(e)}")
                return False
        else:
            print(f"✗ Unsupported database type in DATABASE_URL: {database_url}")
            return False
        
        return True
    except ImportError:
        print("✗ python-dotenv package is not installed. Install it with: pip install python-dotenv")
        return False
    except Exception as e:
        print(f"✗ Error checking database: {str(e)}")
        return False

def main():
    """اجرای تمام بررسی‌ها"""
    print("=== CoinCeeper Environment Setup ===\n")
    
    all_checks_passed = True
    
    # بررسی نسخه پایتون
    if not check_python_version():
        all_checks_passed = False
    
    print("\n=== Checking Dependencies ===")
    if not check_dependencies():
        all_checks_passed = False
    
    print("\n=== Checking Environment Configuration ===")
    if not check_env_file():
        all_checks_passed = False
    
    print("\n=== Checking Database Connection ===")
    if not check_database():
        all_checks_passed = False
    
    print("\n=== Summary ===")
    if all_checks_passed:
        print("✅ All checks passed! Your environment is ready to run CoinCeeper.")
        print("\nStart the application with: python app.py")
    else:
        print("❌ Some checks failed. Please fix the issues before running the application.")
    
    return 0 if all_checks_passed else 1

if __name__ == "__main__":
    sys.exit(main()) 