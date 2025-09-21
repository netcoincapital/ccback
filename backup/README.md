# سیستم بک‌آپ خودکار پایگاه داده CoinCeeper

این سیستم به صورت خودکار از پایگاه‌های داده MySQL شما بک‌آپ روزانه در قالب SQL می‌گیرد.

## ویژگی‌ها

✅ **بک‌آپ خودکار روزانه** - اجرای خودکار در ساعت مشخص  
✅ **پشتیبانی از چندین پایگاه داده** - بک‌آپ همزمان از `coinceeper`، `coincee`، `ironwallet`  
✅ **فشرده‌سازی** - کاهش حجم فایل‌ها با gzip  
✅ **مدیریت فضای دیسک** - حذف خودکار بک‌آپ‌های قدیمی  
✅ **اطلاع‌رسانی ایمیل** - گزارش موفقیت یا خطا  
✅ **لاگ‌گیری کامل** - ثبت تمام فعالیت‌ها  
✅ **مانیتورینگ** - بررسی سلامت سیستم  
✅ **گزارش JSON** - ذخیره گزارش تفصیلی هر بک‌آپ  

## پیش‌نیازها

### نرم‌افزارهای مورد نیاز

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip mysql-client

# CentOS/RHEL
sudo yum install python3 python3-pip mysql

# یا با dnf
sudo dnf install python3 python3-pip mysql
```

### کتابخانه‌های Python

```bash
pip3 install -r requirements.txt
```

محتویات `requirements.txt`:
```
schedule>=1.2.0
python-dotenv>=1.0.0
PyMySQL>=1.0.0
```

## نصب و راه‌اندازی

### 1. کپی فایل‌های پیکربندی

```bash
# کپی فایل تنظیمات
cp backup/.env.example .env

# ویرایش تنظیمات
nano .env
```

### 2. تنظیم متغیرهای محیطی

فایل `.env` را ویرایش کنید:

```env
# اطلاعات اتصال به پایگاه داده
DB_HOST=localhost
DB_USER=your_username
DB_PASSWORD=your_password
DB_NAME=coinceeper

# تنظیمات بک‌آپ
BACKUP_DIR=./backups
BACKUP_RETENTION_DAYS=30
COMPRESS_BACKUPS=true

# زمان‌بندی (فرمت 24 ساعته)
BACKUP_TIME=02:00

# اطلاع‌رسانی ایمیل (اختیاری)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
NOTIFICATION_EMAIL=admin@company.com
```

### 3. تست اولیه

```bash
# تست اتصال و تنظیمات
python3 backup/backup_scheduler.py --manual-backup
```

## روش‌های اجرا

### روش 1: سرویس Systemd (توصیه شده)

```bash
# ایجاد فایل سرویس
sudo python3 backup/backup_scheduler.py --create-service

# فعال‌سازی سرویس
sudo systemctl daemon-reload
sudo systemctl enable coinceeper-backup
sudo systemctl start coinceeper-backup

# بررسی وضعیت
sudo systemctl status coinceeper-backup

# مشاهده لاگ‌ها
sudo journalctl -u coinceeper-backup -f
```

### روش 2: Cron Job

```bash
# باز کردن crontab
crontab -e

# اضافه کردن خط زیر برای اجرای روزانه در ساعت 2 صبح
0 2 * * * cd /path/to/coinceeper && /usr/bin/python3 backup/database_backup.py
```

### روش 3: اجرای مستقیم Scheduler

```bash
# اجرای در پس‌زمینه
nohup python3 backup/backup_scheduler.py > scheduler.log 2>&1 &

# یا در foreground
python3 backup/backup_scheduler.py
```

## دستورات مفید

### بک‌آپ دستی

```bash
# اجرای بک‌آپ فوری
python3 backup/backup_scheduler.py --manual-backup
```

### بررسی وضعیت

```bash
# نمایش وضعیت سیستم
python3 backup/backup_scheduler.py --status
```

### مشاهده لاگ‌ها

```bash
# لاگ بک‌آپ
tail -f Logs/database_backup.log

# لاگ scheduler
tail -f Logs/backup_scheduler.log
```

## ساختار فایل‌های بک‌آپ

```
backups/
├── coinceeper_backup_20250915_020001.sql.gz
├── coincee_backup_20250915_020002.sql.gz
├── ironwallet_backup_20250915_020003.sql.gz
├── backup_report_20250915_020005.json
└── ...
```

### نام‌گذاری فایل‌ها

- فرمت: `{database}_backup_{YYYYMMDD_HHMMSS}.sql[.gz]`
- مثال: `coinceeper_backup_20250915_143022.sql.gz`

### گزارش‌ها

فایل‌های JSON حاوی اطلاعات تفصیلی هر بک‌آپ:

```json
{
  "timestamp": "2025-09-15T02:00:05.123456",
  "duration_seconds": 45.2,
  "successful_backups": 3,
  "failed_backups": 0,
  "total_size_mb": 156.78,
  "backup_files": [
    "coinceeper_backup_20250915_020001.sql.gz",
    "coincee_backup_20250915_020002.sql.gz",
    "ironwallet_backup_20250915_020003.sql.gz"
  ],
  "failed_databases": []
}
```

## بازیابی از بک‌آپ

### بازیابی کامل

```bash
# استخراج فایل فشرده
gunzip coinceeper_backup_20250915_020001.sql.gz

# بازیابی به پایگاه داده
mysql -u username -p coinceeper < coinceeper_backup_20250915_020001.sql
```

### بازیابی جزئی

```bash
# مشاهده محتویات بدون بازیابی
zcat coinceeper_backup_20250915_020001.sql.gz | head -50

# بازیابی فقط یک جدول خاص
zcat coinceeper_backup_20250915_020001.sql.gz | \
mysql -u username -p --one-database coinceeper
```

## مانیتورینگ و نگهداری

### بررسی سلامت سیستم

سیستم هر 30 دقیقه خودکار بررسی می‌کند:

- آیا بک‌آپ اخیر انجام شده؟
- آیا بک‌آپ موفقیت‌آمیز بوده؟
- آیا بک‌آپ فعلی خیلی طول کشیده؟

### اطلاع‌رسانی‌ها

در صورت تنظیم ایمیل، موارد زیر گزارش می‌شوند:

- ✅ بک‌آپ موفق روزانه
- ❌ خطاهای بک‌آپ
- ⚠️ هشدارهای سیستم

### لاگ‌ها

```bash
# مکان لاگ‌ها
Logs/
├── database_backup.log      # لاگ عملیات بک‌آپ
├── backup_scheduler.log     # لاگ زمان‌بندی
└── ...
```

## عیب‌یابی

### خطاهای رایج

#### 1. خطای اتصال به پایگاه داده

```
خطا در ایجاد بک‌آپ: Access denied for user
```

**حل:**
- بررسی اطلاعات اتصال در `.env`
- اطمینان از وجود دسترسی کاربر به پایگاه داده

#### 2. فضای دیسک کافی نیست

```
خطا در ایجاد بک‌آپ: No space left on device
```

**حل:**
- بررسی فضای دیسک: `df -h`
- کاهش `BACKUP_RETENTION_DAYS`
- پاکسازی دستی فایل‌های قدیمی

#### 3. mysqldump یافت نشد

```
mysqldump یافت نشد
```

**حل:**
```bash
# Ubuntu/Debian
sudo apt install mysql-client

# CentOS/RHEL
sudo yum install mysql
```

### بررسی وضعیت

```bash
# تست اتصال به پایگاه داده
mysql -h localhost -u your_user -p -e "SELECT 1;"

# بررسی فضای دیسک
df -h ./backups/

# تست دسترسی نوشتن
touch ./backups/test_write && rm ./backups/test_write
```

## تنظیمات پیشرفته

### تنظیم پایگاه‌های داده

در فایل `backup/database_backup.py` خط 47-51:

```python
self.databases = [
    os.getenv('DB_NAME', 'coinceeper'),
    'coincee',
    'ironwallet',
    'your_additional_db'  # اضافه کردن پایگاه داده جدید
]
```

### تنظیم mysqldump

در فایل `backup/database_backup.py` خط 118-130:

```python
cmd = [
    'mysqldump',
    f'--host={self.db_host}',
    f'--user={self.db_user}',
    f'--password={self.db_password}',
    '--single-transaction',      # تراکنش یکپارچه
    '--routines',               # شامل stored procedures
    '--triggers',               # شامل triggers
    '--events',                 # شامل events
    '--hex-blob',               # داده‌های باینری
    '--default-character-set=utf8mb4',  # پشتیبانی UTF-8
    '--add-drop-database',      # DROP DATABASE قبل از CREATE
    '--create-options',         # گزینه‌های CREATE TABLE
    database_name
]
```

### تنظیم اطلاع‌رسانی

برای Gmail:

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password  # نه پسورد اصلی!
```

**نکته:** برای Gmail باید App Password استفاده کنید.

## امنیت

### محافظت از اطلاعات حساس

```bash
# تنظیم دسترسی فایل .env
chmod 600 .env

# تنظیم دسترسی پوشه بک‌آپ
chmod 700 backups/
```

### رمزگذاری بک‌آپ‌ها (اختیاری)

```bash
# رمزگذاری فایل بک‌آپ
gpg --symmetric --cipher-algo AES256 backup_file.sql.gz

# رمزگشایی
gpg --decrypt backup_file.sql.gz.gpg > backup_file.sql.gz
```

## پشتیبانی

### لاگ‌ها و عیب‌یابی

همیشه لاگ‌ها را بررسی کنید:

```bash
# آخرین خطاها
grep -i error Logs/database_backup.log

# آخرین بک‌آپ‌ها
grep -i "بک‌آپ.*کامل شد" Logs/database_backup.log | tail -5
```

### تماس با پشتیبانی

در صورت بروز مشکل، اطلاعات زیر را آماده کنید:

1. محتویات فایل لاگ
2. تنظیمات `.env` (بدون پسوردها)
3. نسخه MySQL: `mysql --version`
4. نسخه Python: `python3 --version`
5. سیستم‌عامل: `cat /etc/os-release`

---

**نکته:** این سیستم برای محیط‌های production طراحی شده و تمام جنبه‌های امنیت، کارایی و قابلیت اطمینان را در نظر گرفته است.


