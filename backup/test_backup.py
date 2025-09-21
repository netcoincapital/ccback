#!/usr/bin/env python3
"""
Test script for CoinCeeper Database Backup System
تست سیستم بک‌آپ پایگاه داده

This script tests the backup system functionality
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from backup.database_backup import DatabaseBackup


def test_configuration():
    """Test configuration validation"""
    print("Testing configuration...")
    
    try:
        backup = DatabaseBackup()
        backup.validate_config()
        print("✅ Configuration validation passed")
        return True
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        return False


def test_backup_creation():
    """Test backup creation with temporary directory"""
    print("Testing backup creation...")
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Override backup directory for testing
        original_backup_dir = os.getenv('BACKUP_DIR')
        os.environ['BACKUP_DIR'] = temp_dir
        
        try:
            backup = DatabaseBackup()
            
            # Test with a small database or create a test database
            # For safety, we'll just test the first database
            test_db = backup.databases[0] if backup.databases else 'coinceeper'
            
            print(f"Creating test backup for database: {test_db}")
            backup_path = backup.create_backup(test_db)
            
            if backup_path.exists():
                file_size = backup_path.stat().st_size
                print(f"✅ Backup created successfully: {backup_path.name} ({file_size} bytes)")
                return True
            else:
                print("❌ Backup file not created")
                return False
                
        except Exception as e:
            print(f"❌ Backup creation failed: {e}")
            return False
        finally:
            # Restore original backup directory
            if original_backup_dir:
                os.environ['BACKUP_DIR'] = original_backup_dir
            elif 'BACKUP_DIR' in os.environ:
                del os.environ['BACKUP_DIR']


def test_cleanup_functionality():
    """Test cleanup functionality"""
    print("Testing cleanup functionality...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create some fake old backup files
        temp_path = Path(temp_dir)
        
        # Create old files (simulate files older than retention period)
        old_file1 = temp_path / "old_backup_20230101_120000.sql.gz"
        old_file2 = temp_path / "old_backup_20230102_120000.sql.gz"
        recent_file = temp_path / "recent_backup_20250915_120000.sql.gz"
        
        # Create the files
        for file_path in [old_file1, old_file2, recent_file]:
            file_path.touch()
            # Set old modification time for old files
            if 'old_backup' in file_path.name:
                # Set modification time to 40 days ago
                old_timestamp = datetime.now().timestamp() - (40 * 24 * 60 * 60)
                os.utime(file_path, (old_timestamp, old_timestamp))
        
        # Override backup directory and retention period for testing
        original_backup_dir = os.getenv('BACKUP_DIR')
        original_retention = os.getenv('BACKUP_RETENTION_DAYS')
        
        os.environ['BACKUP_DIR'] = temp_dir
        os.environ['BACKUP_RETENTION_DAYS'] = '30'
        
        try:
            backup = DatabaseBackup()
            backup.cleanup_old_backups()
            
            # Check results
            remaining_files = list(temp_path.glob('*_backup_*.sql*'))
            
            if len(remaining_files) == 1 and recent_file in remaining_files:
                print("✅ Cleanup functionality works correctly")
                return True
            else:
                print(f"❌ Cleanup failed. Remaining files: {[f.name for f in remaining_files]}")
                return False
                
        except Exception as e:
            print(f"❌ Cleanup test failed: {e}")
            return False
        finally:
            # Restore original values
            if original_backup_dir:
                os.environ['BACKUP_DIR'] = original_backup_dir
            elif 'BACKUP_DIR' in os.environ:
                del os.environ['BACKUP_DIR']
                
            if original_retention:
                os.environ['BACKUP_RETENTION_DAYS'] = original_retention
            elif 'BACKUP_RETENTION_DAYS' in os.environ:
                del os.environ['BACKUP_RETENTION_DAYS']


def test_logging():
    """Test logging functionality"""
    print("Testing logging...")
    
    try:
        backup = DatabaseBackup()
        
        # Test logging
        backup.logger.info("Test log message")
        
        # Check if log file was created
        log_file = Path('./Logs/database_backup.log')
        if log_file.exists():
            print("✅ Logging works correctly")
            return True
        else:
            print("❌ Log file not created")
            return False
            
    except Exception as e:
        print(f"❌ Logging test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("CoinCeeper Database Backup System Test")
    print("تست سیستم بک‌آپ پایگاه داده")
    print("=" * 60)
    
    tests = [
        ("Configuration", test_configuration),
        ("Logging", test_logging),
        ("Cleanup Functionality", test_cleanup_functionality),
        ("Backup Creation", test_backup_creation),  # This should be last as it's most likely to fail
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            if test_func():
                passed += 1
            else:
                print(f"Test failed: {test_name}")
        except Exception as e:
            print(f"Test error in {test_name}: {e}")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("✅ All tests passed! Backup system is ready.")
        return True
    else:
        print("❌ Some tests failed. Please check the configuration.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


