#!/usr/bin/env python3
"""
Automated Database Backup System for CoinCeeper
================================================

این سیستم به صورت خودکار از پایگاه‌های داده MySQL بک‌آپ SQL می‌گیرد
Features:
- بک‌آپ روزانه خودکار
- فشرده‌سازی فایل‌ها
- مدیریت فضای دیسک (حذف بک‌آپ‌های قدیمی)
- لاگ‌گیری کامل
- اطلاع‌رسانی در صورت خطا

Author: CoinCeeper Development Team
Date: 2025
"""

import os
import sys
import logging
import subprocess
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

class DatabaseBackup:
    """کلاس مدیریت بک‌آپ پایگاه داده"""
    
    def __init__(self):
        """تنظیمات اولیه"""
        # تنظیمات پایگاه داده
        self.db_host = os.getenv('DB_HOST', 'localhost')
        self.db_user = os.getenv('DB_USER')
        self.db_password = os.getenv('DB_PASSWORD')
        self.databases = [
            os.getenv('DB_NAME', 'coinceeper'),
            'coincee',  # پایگاه داده اضافی
            'ironwallet'  # پایگاه داده اضافی
        ]
        
        # تنظیمات بک‌آپ
        self.backup_dir = Path(os.getenv('BACKUP_DIR', './backups'))
        self.backup_retention_days = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))
        self.compress_backups = os.getenv('COMPRESS_BACKUPS', 'true').lower() == 'true'
        
        # تنظیمات ایمیل (اختیاری)
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.notification_email = os.getenv('NOTIFICATION_EMAIL')
        
        # ایجاد دایرکتوری بک‌آپ
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # تنظیم لاگینگ
        self.setup_logging()
        
    def setup_logging(self):
        """تنظیم سیستم لاگ‌گیری"""
        log_dir = Path('./Logs')
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / 'database_backup.log'
        
        # پیکربندی logger
        self.logger = logging.getLogger('DatabaseBackup')
        self.logger.setLevel(logging.INFO)
        
        # حذف handler های قبلی
        self.logger.handlers.clear()
        
        # File handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # فرمت لاگ
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def validate_config(self):
        """بررسی صحت تنظیمات"""
        if not self.db_user or not self.db_password:
            raise ValueError("اطلاعات اتصال به پایگاه داده (DB_USER, DB_PASSWORD) تنظیم نشده‌اند")
        
        # بررسی وجود mysqldump
        try:
            subprocess.run(['mysqldump', '--version'], 
                         capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("mysqldump یافت نشد. لطفاً MySQL Client Tools را نصب کنید")
    
    def create_backup(self, database_name):
        """ایجاد بک‌آپ برای یک پایگاه داده"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"{database_name}_backup_{timestamp}.sql"
        backup_path = self.backup_dir / backup_filename
        
        self.logger.info(f"شروع بک‌آپ پایگاه داده: {database_name}")
        
        try:
            # دستور mysqldump
            cmd = [
                'mysqldump',
                f'--host={self.db_host}',
                f'--user={self.db_user}',
                f'--password={self.db_password}',
                '--single-transaction',
                '--routines',
                '--triggers',
                '--events',
                '--hex-blob',
                '--default-character-set=utf8mb4',
                '--add-drop-database',
                '--create-options',
                database_name
            ]
            
            # اجرای دستور و ذخیره خروجی
            with open(backup_path, 'w', encoding='utf-8') as backup_file:
                result = subprocess.run(
                    cmd,
                    stdout=backup_file,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True
                )
            
            # بررسی اندازه فایل
            file_size = backup_path.stat().st_size
            if file_size == 0:
                raise RuntimeError(f"فایل بک‌آپ خالی است: {backup_path}")
            
            # فشرده‌سازی در صورت نیاز
            if self.compress_backups:
                compressed_path = self.compress_backup(backup_path)
                backup_path = compressed_path
                file_size = backup_path.stat().st_size
            
            self.logger.info(
                f"بک‌آپ {database_name} با موفقیت ایجاد شد: {backup_path.name} "
                f"({file_size / 1024 / 1024:.2f} MB)"
            )
            
            return backup_path
            
        except subprocess.CalledProcessError as e:
            error_msg = f"خطا در ایجاد بک‌آپ {database_name}: {e.stderr}"
            self.logger.error(error_msg)
            # حذف فایل ناقص
            if backup_path.exists():
                backup_path.unlink()
            raise RuntimeError(error_msg)
        
        except Exception as e:
            error_msg = f"خطای غیرمنتظره در بک‌آپ {database_name}: {str(e)}"
            self.logger.error(error_msg)
            if backup_path.exists():
                backup_path.unlink()
            raise RuntimeError(error_msg)
    
    def compress_backup(self, backup_path):
        """فشرده‌سازی فایل بک‌آپ"""
        compressed_path = backup_path.with_suffix(backup_path.suffix + '.gz')
        
        try:
            with open(backup_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # حذف فایل اصلی
            backup_path.unlink()
            
            return compressed_path
            
        except Exception as e:
            self.logger.error(f"خطا در فشرده‌سازی {backup_path}: {str(e)}")
            if compressed_path.exists():
                compressed_path.unlink()
            return backup_path
    
    def cleanup_old_backups(self):
        """حذف بک‌آپ‌های قدیمی"""
        cutoff_date = datetime.now() - timedelta(days=self.backup_retention_days)
        deleted_count = 0
        freed_space = 0
        
        self.logger.info(f"شروع پاکسازی بک‌آپ‌های قدیمی‌تر از {self.backup_retention_days} روز")
        
        try:
            for backup_file in self.backup_dir.glob('*_backup_*.sql*'):
                file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                
                if file_mtime < cutoff_date:
                    file_size = backup_file.stat().st_size
                    backup_file.unlink()
                    deleted_count += 1
                    freed_space += file_size
                    self.logger.info(f"حذف شد: {backup_file.name}")
            
            if deleted_count > 0:
                self.logger.info(
                    f"پاکسازی کامل شد: {deleted_count} فایل حذف شد، "
                    f"{freed_space / 1024 / 1024:.2f} MB آزاد شد"
                )
            else:
                self.logger.info("فایل قدیمی برای حذف یافت نشد")
                
        except Exception as e:
            self.logger.error(f"خطا در پاکسازی بک‌آپ‌های قدیمی: {str(e)}")
    
    def send_notification(self, subject, message, is_error=False):
        """ارسال اطلاع‌رسانی ایمیل"""
        if not all([self.smtp_server, self.smtp_username, self.smtp_password, self.notification_email]):
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_username
            msg['To'] = self.notification_email
            msg['Subject'] = f"[CoinCeeper Backup] {subject}"
            
            msg.attach(MIMEText(message, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
            server.quit()
            
            self.logger.info("اطلاع‌رسانی ایمیل ارسال شد")
            
        except Exception as e:
            self.logger.error(f"خطا در ارسال ایمیل: {str(e)}")
    
    def create_backup_report(self, successful_backups, failed_backups, start_time, end_time):
        """ایجاد گزارش بک‌آپ"""
        duration = end_time - start_time
        total_size = 0
        
        for backup_path in successful_backups:
            if backup_path.exists():
                total_size += backup_path.stat().st_size
        
        report = {
            'timestamp': end_time.isoformat(),
            'duration_seconds': duration.total_seconds(),
            'successful_backups': len(successful_backups),
            'failed_backups': len(failed_backups),
            'total_size_mb': total_size / 1024 / 1024,
            'backup_files': [str(p.name) for p in successful_backups],
            'failed_databases': failed_backups
        }
        
        # ذخیره گزارش
        report_file = self.backup_dir / f"backup_report_{end_time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return report
    
    def run_backup(self):
        """اجرای فرآیند کامل بک‌آپ"""
        start_time = datetime.now()
        successful_backups = []
        failed_backups = []
        
        self.logger.info("=" * 60)
        self.logger.info("شروع فرآیند بک‌آپ خودکار پایگاه داده")
        self.logger.info("=" * 60)
        
        try:
            # بررسی تنظیمات
            self.validate_config()
            
            # بک‌آپ هر پایگاه داده
            for database in self.databases:
                try:
                    backup_path = self.create_backup(database)
                    successful_backups.append(backup_path)
                except Exception as e:
                    self.logger.error(f"بک‌آپ {database} ناموفق بود: {str(e)}")
                    failed_backups.append(database)
            
            # پاکسازی فایل‌های قدیمی
            self.cleanup_old_backups()
            
            end_time = datetime.now()
            
            # ایجاد گزارش
            report = self.create_backup_report(successful_backups, failed_backups, start_time, end_time)
            
            # لاگ نهایی
            if failed_backups:
                self.logger.warning(
                    f"بک‌آپ با خطا کامل شد: {len(successful_backups)} موفق، "
                    f"{len(failed_backups)} ناموفق در {report['duration_seconds']:.1f} ثانیه"
                )
                
                # ارسال اطلاع‌رسانی خطا
                error_message = f"""
بک‌آپ پایگاه داده با خطا کامل شد:

موفق: {len(successful_backups)} پایگاه داده
ناموفق: {len(failed_backups)} پایگاه داده ({', '.join(failed_backups)})
مدت زمان: {report['duration_seconds']:.1f} ثانیه
حجم کل: {report['total_size_mb']:.2f} MB

لطفاً لاگ‌ها را بررسی کنید.
                """
                self.send_notification("خطا در بک‌آپ", error_message.strip(), is_error=True)
                
            else:
                self.logger.info(
                    f"بک‌آپ با موفقیت کامل شد: {len(successful_backups)} پایگاه داده "
                    f"در {report['duration_seconds']:.1f} ثانیه، حجم کل: {report['total_size_mb']:.2f} MB"
                )
                
                # ارسال اطلاع‌رسانی موفقیت
                success_message = f"""
بک‌آپ روزانه با موفقیت انجام شد:

تعداد پایگاه داده: {len(successful_backups)}
مدت زمان: {report['duration_seconds']:.1f} ثانیه  
حجم کل: {report['total_size_mb']:.2f} MB

فایل‌های بک‌آپ:
{chr(10).join('- ' + name for name in report['backup_files'])}
                """
                self.send_notification("بک‌آپ موفق", success_message.strip())
            
            return len(failed_backups) == 0
            
        except Exception as e:
            error_msg = f"خطای کلی در فرآیند بک‌آپ: {str(e)}"
            self.logger.error(error_msg)
            self.send_notification("خطای کلی در بک‌آپ", error_msg, is_error=True)
            return False
        
        finally:
            self.logger.info("=" * 60)
            self.logger.info("پایان فرآیند بک‌آپ")
            self.logger.info("=" * 60)


def main():
    """تابع اصلی"""
    backup_system = DatabaseBackup()
    
    try:
        success = backup_system.run_backup()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        backup_system.logger.info("بک‌آپ توسط کاربر متوقف شد")
        sys.exit(1)
    except Exception as e:
        print(f"خطای غیرمنتظره: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()


