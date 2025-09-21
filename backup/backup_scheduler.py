#!/usr/bin/env python3
"""
Database Backup Scheduler for CoinCeeper
========================================

زمان‌بندی خودکار برای اجرای بک‌آپ روزانه پایگاه داده
این اسکریپت می‌تواند به عنوان سرویس سیستمی یا با cron اجرا شود

Features:
- اجرای روزانه در ساعت مشخص
- مانیتورینگ وضعیت
- مدیریت خطاها
- لاگ‌گیری کامل

Author: CoinCeeper Development Team
Date: 2025
"""

import os
import sys
import time
import schedule
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# اضافه کردن پوشه والد به path
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

# Import backup system
from backup.database_backup import DatabaseBackup

class BackupScheduler:
    """کلاس زمان‌بندی بک‌آپ"""
    
    def __init__(self):
        """تنظیمات اولیه"""
        # تنظیمات زمان‌بندی
        self.backup_time = os.getenv('BACKUP_TIME', '02:00')  # ساعت 2 صبح به طور پیش‌فرض
        self.timezone_offset = int(os.getenv('TIMEZONE_OFFSET', '0'))  # اختلاف ساعت با UTC
        
        # تنظیمات مانیتورینگ
        self.max_backup_duration = int(os.getenv('MAX_BACKUP_DURATION_MINUTES', '60'))  # حداکثر 60 دقیقه
        self.health_check_interval = int(os.getenv('HEALTH_CHECK_INTERVAL_MINUTES', '30'))  # هر 30 دقیقه
        
        # وضعیت سیستم
        self.is_running = False
        self.last_backup_time = None
        self.last_backup_success = None
        self.current_backup_thread = None
        
        # تنظیم لاگینگ
        self.setup_logging()
        
        # ایجاد instance بک‌آپ
        self.backup_system = DatabaseBackup()
    
    def setup_logging(self):
        """تنظیم سیستم لاگ‌گیری"""
        log_dir = Path('./Logs')
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / 'backup_scheduler.log'
        
        # پیکربندی logger
        self.logger = logging.getLogger('BackupScheduler')
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
    
    def run_backup_job(self):
        """اجرای job بک‌آپ در thread جداگانه"""
        backup_start_time = datetime.now()
        self.logger.info(f"شروع job بک‌آپ روزانه در {backup_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # اجرای بک‌آپ
            success = self.backup_system.run_backup()
            
            # ثبت نتیجه
            self.last_backup_time = backup_start_time
            self.last_backup_success = success
            
            backup_end_time = datetime.now()
            duration = backup_end_time - backup_start_time
            
            if success:
                self.logger.info(f"job بک‌آپ روزانه با موفقیت کامل شد در {duration.total_seconds():.1f} ثانیه")
            else:
                self.logger.error(f"job بک‌آپ روزانه با خطا کامل شد در {duration.total_seconds():.1f} ثانیه")
        
        except Exception as e:
            self.logger.error(f"خطای غیرمنتظره در job بک‌آپ: {str(e)}", exc_info=True)
            self.last_backup_time = backup_start_time
            self.last_backup_success = False
        
        finally:
            self.current_backup_thread = None
    
    def scheduled_backup(self):
        """تابع زمان‌بندی شده برای بک‌آپ"""
        # بررسی اینکه آیا بک‌آپ قبلی هنوز در حال اجراست
        if self.current_backup_thread and self.current_backup_thread.is_alive():
            self.logger.warning("بک‌آپ قبلی هنوز در حال اجراست، job جدید رد شد")
            return
        
        # شروع thread جدید برای بک‌آپ
        self.current_backup_thread = threading.Thread(target=self.run_backup_job)
        self.current_backup_thread.daemon = True
        self.current_backup_thread.start()
    
    def health_check(self):
        """بررسی سلامت سیستم بک‌آپ"""
        now = datetime.now()
        
        # بررسی آیا بک‌آپ اخیر انجام شده
        if self.last_backup_time:
            time_since_last_backup = now - self.last_backup_time
            
            # اگر بیش از 25 ساعت از آخرین بک‌آپ گذشته باشد
            if time_since_last_backup > timedelta(hours=25):
                self.logger.warning(
                    f"هشدار: {time_since_last_backup.total_seconds() / 3600:.1f} ساعت "
                    f"از آخرین بک‌آپ گذشته است"
                )
            
            # بررسی وضعیت آخرین بک‌آپ
            if self.last_backup_success is False:
                self.logger.warning("هشدار: آخرین بک‌آپ ناموفق بود")
        
        # بررسی thread بک‌آپ در حال اجرا
        if self.current_backup_thread and self.current_backup_thread.is_alive():
            # بررسی اینکه آیا بک‌آپ خیلی طول کشیده
            if self.last_backup_time:
                backup_duration = now - self.last_backup_time
                if backup_duration > timedelta(minutes=self.max_backup_duration):
                    self.logger.error(
                        f"خطر: بک‌آپ بیش از {self.max_backup_duration} دقیقه طول کشیده "
                        f"({backup_duration.total_seconds() / 60:.1f} دقیقه)"
                    )
    
    def get_status(self):
        """دریافت وضعیت فعلی سیستم"""
        status = {
            'is_running': self.is_running,
            'backup_time': self.backup_time,
            'last_backup_time': self.last_backup_time.isoformat() if self.last_backup_time else None,
            'last_backup_success': self.last_backup_success,
            'backup_in_progress': self.current_backup_thread and self.current_backup_thread.is_alive(),
            'next_backup': None
        }
        
        # محاسبه زمان بک‌آپ بعدی
        if self.is_running:
            try:
                next_run = schedule.next_run()
                if next_run:
                    status['next_backup'] = next_run.isoformat()
            except:
                pass
        
        return status
    
    def start(self):
        """شروع زمان‌بندی بک‌آپ"""
        if self.is_running:
            self.logger.warning("زمان‌بندی بک‌آپ قبلاً شروع شده است")
            return
        
        self.logger.info("شروع سیستم زمان‌بندی بک‌آپ خودکار")
        self.logger.info(f"زمان بک‌آپ روزانه: {self.backup_time}")
        self.logger.info(f"فاصله بررسی سلامت: {self.health_check_interval} دقیقه")
        
        try:
            # تنظیم زمان‌بندی روزانه
            schedule.every().day.at(self.backup_time).do(self.scheduled_backup)
            
            # تنظیم بررسی سلامت
            schedule.every(self.health_check_interval).minutes.do(self.health_check)
            
            self.is_running = True
            
            # حلقه اصلی
            while self.is_running:
                try:
                    schedule.run_pending()
                    time.sleep(60)  # چک کردن هر دقیقه
                except KeyboardInterrupt:
                    self.logger.info("دریافت سیگنال توقف از کاربر")
                    break
                except Exception as e:
                    self.logger.error(f"خطا در حلقه اصلی زمان‌بندی: {str(e)}", exc_info=True)
                    time.sleep(60)
        
        except Exception as e:
            self.logger.error(f"خطا در شروع زمان‌بندی: {str(e)}", exc_info=True)
        
        finally:
            self.stop()
    
    def stop(self):
        """توقف زمان‌بندی بک‌آپ"""
        self.logger.info("توقف سیستم زمان‌بندی بک‌آپ")
        
        self.is_running = False
        
        # انتظار برای تمام شدن thread بک‌آپ در حال اجرا
        if self.current_backup_thread and self.current_backup_thread.is_alive():
            self.logger.info("انتظار برای تمام شدن بک‌آپ در حال اجرا...")
            self.current_backup_thread.join(timeout=300)  # انتظار حداکثر 5 دقیقه
        
        # پاک کردن تمام job های زمان‌بندی شده
        schedule.clear()
        
        self.logger.info("سیستم زمان‌بندی بک‌آپ متوقف شد")
    
    def run_manual_backup(self):
        """اجرای دستی بک‌آپ"""
        self.logger.info("درخواست اجرای دستی بک‌آپ")
        
        if self.current_backup_thread and self.current_backup_thread.is_alive():
            self.logger.warning("بک‌آپ در حال اجراست، نمی‌توان بک‌آپ دستی اجرا کرد")
            return False
        
        # اجرای بک‌آپ در thread جداگانه
        self.current_backup_thread = threading.Thread(target=self.run_backup_job)
        self.current_backup_thread.daemon = True
        self.current_backup_thread.start()
        
        return True


def create_systemd_service():
    """ایجاد فایل سرویس systemd"""
    service_content = f"""[Unit]
Description=CoinCeeper Database Backup Scheduler
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory={Path(__file__).parent.parent.absolute()}
Environment=PATH=/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/python3 {Path(__file__).absolute()}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    
    service_file = Path('/etc/systemd/system/coinceeper-backup.service')
    
    try:
        with open(service_file, 'w') as f:
            f.write(service_content)
        
        print(f"فایل سرویس systemd ایجاد شد: {service_file}")
        print("برای فعال‌سازی سرویس:")
        print("sudo systemctl daemon-reload")
        print("sudo systemctl enable coinceeper-backup")
        print("sudo systemctl start coinceeper-backup")
        
    except PermissionError:
        print("خطا: دسترسی کافی برای ایجاد فایل سرویس وجود ندارد")
        print("لطفاً با sudo اجرا کنید")


def create_cron_job():
    """راهنمای ایجاد cron job"""
    cron_command = f"0 2 * * * cd {Path(__file__).parent.parent.absolute()} && /usr/bin/python3 backup/database_backup.py"
    
    print("برای تنظیم cron job:")
    print("crontab -e")
    print("سپس خط زیر را اضافه کنید:")
    print(cron_command)
    print()
    print("یا برای اجرای scheduler به صورت مداوم:")
    print(f"nohup python3 {Path(__file__).absolute()} &")


def main():
    """تابع اصلی"""
    import argparse
    
    parser = argparse.ArgumentParser(description='CoinCeeper Database Backup Scheduler')
    parser.add_argument('--create-service', action='store_true', 
                       help='ایجاد فایل سرویس systemd')
    parser.add_argument('--show-cron', action='store_true', 
                       help='نمایش راهنمای تنظیم cron job')
    parser.add_argument('--manual-backup', action='store_true', 
                       help='اجرای دستی بک‌آپ')
    parser.add_argument('--status', action='store_true', 
                       help='نمایش وضعیت فعلی')
    
    args = parser.parse_args()
    
    if args.create_service:
        create_systemd_service()
        return
    
    if args.show_cron:
        create_cron_job()
        return
    
    # ایجاد scheduler
    scheduler = BackupScheduler()
    
    if args.manual_backup:
        print("اجرای بک‌آپ دستی...")
        success = scheduler.backup_system.run_backup()
        sys.exit(0 if success else 1)
    
    if args.status:
        status = scheduler.get_status()
        print("وضعیت سیستم بک‌آپ:")
        for key, value in status.items():
            print(f"  {key}: {value}")
        return
    
    # اجرای scheduler
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\nمتوقف شد توسط کاربر")
    except Exception as e:
        print(f"خطا: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()


