# راهنمای اصلاح مشکلات UI دیتابیس
# Database UI Fix Guide

## مشکلات شناسایی شده در phpMyAdmin:

### ❌ **مشکلات فعلی:**
1. **WalletID و UserID**: به صورت dropdown نمایش داده می‌شوند (باید input باشند)
2. **فیلدهای Direction/Status**: به صورت text input هستند (باید dropdown باشند)
3. **فیلد RawData**: مربع بزرگ JSON که فضای زیادی اشغال می‌کند
4. **فیلدهای Boolean**: به صورت 0/1 نامفهوم نمایش داده می‌شوند

### ✅ **راه حل‌های پیاده شده:**

#### 1. **تبدیل فیلدهای مناسب به ENUM (Dropdown)**
```sql
-- Direction در transfers و balance_update_log
Direction ENUM('inbound', 'outbound')

-- Status در transfers  
Status ENUM('pending', 'confirmed', 'failed')

-- AssetType در transfers
AssetType ENUM('native', 'token')

-- DeviceType در user_devices
DeviceType ENUM('android', 'ios', 'web', 'desktop')
```

#### 2. **تبدیل Boolean ها به ENUM واضح**
```sql
-- به جای BOOLEAN که 0/1 نمایش می‌دهد
IsMultiSig ENUM('0', '1') COMMENT '0=خیر, 1=بله'
IsToken ENUM('0', '1') COMMENT '0=ارز اصلی, 1=توکن'
IsSuccessful ENUM('0', '1') COMMENT '0=ناموفق, 1=موفق'
```

#### 3. **اصلاح نمایش RawData**
```sql
-- تبدیل از JSON به TEXT برای نمایش بهتر
RawData TEXT DEFAULT NULL COMMENT 'داده‌های خام به صورت JSON'
```

#### 4. **بهبود نمایش ID ها**
```sql
-- اضافه کردن ZEROFILL برای نمایش بهتر
ID INT NOT NULL AUTO_INCREMENT ZEROFILL
```

## نحوه اعمال تغییرات:

### روش 1: استفاده از اسکریپت PHP (توصیه شده)
```bash
# 1. ویرایش رمز عبور در فایل apply_ui_fixes.php
# 2. اجرای اسکریپت
php apply_ui_fixes.php
```

### روش 2: اجرای مستقیم SQL
```bash
# در phpMyAdmin یا MySQL CLI
mysql -u coincee -p coincee < fix_database_ui_issues.sql
```

### روش 3: کپی و پیست در phpMyAdmin
1. باز کردن فایل `fix_database_ui_issues.sql`
2. کپی کردن محتویات
3. رفتن به phpMyAdmin → SQL Tab
4. پیست کردن و اجرا

## تست تغییرات:

### بعد از اعمال تغییرات، بررسی کنید:

#### 1. **فیلدهای Dropdown:**
- `transfers.Direction` → باید گزینه‌های "inbound/outbound" داشته باشد
- `transfers.Status` → باید گزینه‌های "pending/confirmed/failed" داشته باشد
- `transfers.AssetType` → باید گزینه‌های "native/token" داشته باشد

#### 2. **فیلدهای Input:**
- `wallets.WalletID` → باید text input باشد
- `users.UserID` → باید text input باشد
- `userholding.UserID` → باید text input باشد

#### 3. **فیلد RawData:**
- `userholding.RawData` → باید textarea کوچک باشد (نه مربع بزرگ)

#### 4. **فیلدهای Boolean:**
- همه فیلدهای Boolean باید گزینه‌های "0/1" با توضیح داشته باشند

## اگر مشکلی پیش آمد:

### خطاهای محتمل:
```sql
-- اگر جدول در حال استفاده است
ERROR 1192: Can't execute the given command because you have active locked tables

-- راه حل:
UNLOCK TABLES;
```

```sql
-- اگر داده‌های موجود با ENUM سازگار نیستند
ERROR 1265: Data truncated for column 'Direction'

-- راه حل: ابتدا داده‌های نامعتبر را پاک کنید
UPDATE transfers SET Direction = 'inbound' WHERE Direction NOT IN ('inbound', 'outbound');
```

### بازگرداندن تغییرات:
اگر مشکلی پیش آمد، می‌توانید با اجرای دوباره `create_database_tables.sql` جداول را به حالت قبل برگردانید.

## نتیجه انتظاری:

### ✅ **بعد از اصلاح:**
- **WalletID/UserID**: Text input برای وارد کردن دستی
- **Direction/Status**: Dropdown با گزینه‌های مشخص
- **RawData**: Textarea کوچک و قابل مدیریت
- **Boolean Fields**: گزینه‌های واضح 0/1 با توضیح
- **ID Fields**: نمایش بهتر با padding صفر

### 📱 **تجربه کاربری بهتر در phpMyAdmin:**
- سرعت بیشتر در ویرایش رکوردها
- کاهش خطاهای ورودی
- رابط کاربری تمیزتر و منظم‌تر
- نمایش بهتر داده‌های طولانی

---

## نکات مهم:

1. **Backup**: حتماً قبل از اعمال تغییرات، backup از دیتابیس تهیه کنید
2. **Test Environment**: ابتدا روی دیتابیس تست آزمایش کنید
3. **Browser Refresh**: بعد از اعمال تغییرات، phpMyAdmin را refresh کنید
4. **Cache Clear**: ممکن است نیاز باشد cache مرورگر را پاک کنید

## پشتیبانی:
اگر مشکلی پیش آمد، فایل‌های زیر را بررسی کنید:
- `fix_database_ui_issues.sql` - تغییرات SQL
- `apply_ui_fixes.php` - اسکریپت اعمال تغییرات
- `create_database_tables.sql` - ساختار اصلی جداول (برای بازگردانی)

