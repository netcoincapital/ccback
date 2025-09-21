-- اصلاح مشکلات UI در phpMyAdmin (نسخه ایمن)
-- Fix UI issues in phpMyAdmin (Safe Version)

-- ابتدا بررسی می‌کنیم که کدام جداول وجود دارند
-- First check which tables exist

-- 1. اصلاح جدول userholding (اگر وجود داشته باشد)
-- Fix userholding table (if exists)
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'userholding') > 0,
    'ALTER TABLE `userholding` 
     MODIFY COLUMN `IsToken` ENUM(''0'', ''1'') NOT NULL DEFAULT ''0'' COMMENT ''0=ارز اصلی, 1=توکن'',
     MODIFY COLUMN `RawData` TEXT DEFAULT NULL COMMENT ''داده‌های خام به صورت JSON'';',
    'SELECT ''Table userholding does not exist'' as warning;'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2. اصلاح جدول users (اگر وجود داشته باشد)
-- Fix users table (if exists)
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users') > 0,
    'ALTER TABLE `users` 
     MODIFY COLUMN `ID` INT NOT NULL AUTO_INCREMENT,
     COMMENT = ''جدول کاربران سیستم'';',
    'SELECT ''Table users does not exist'' as warning;'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 3. اصلاح جدول wallets (اگر وجود داشته باشد)
-- Fix wallets table (if exists)
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'wallets') > 0,
    'ALTER TABLE `wallets` 
     MODIFY COLUMN `IsMultiSig` ENUM(''0'', ''1'') NOT NULL DEFAULT ''0'' COMMENT ''0=خیر, 1=بله'',
     COMMENT = ''جدول کیف پول‌های کاربران'';',
    'SELECT ''Table wallets does not exist'' as warning;'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 4. اصلاح جدول currencies (اگر وجود داشته باشد)
-- Fix currencies table (if exists)
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'currencies') > 0,
    'ALTER TABLE `currencies` 
     MODIFY COLUMN `IsToken` ENUM(''0'', ''1'') NOT NULL DEFAULT ''0'' COMMENT ''0=ارز اصلی, 1=توکن'',
     COMMENT = ''جدول ارزها و توکن‌ها'';',
    'SELECT ''Table currencies does not exist'' as warning;'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 5. اصلاح جدول blockchains (اگر وجود داشته باشد)
-- Fix blockchains table (if exists)
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'blockchains') > 0,
    'ALTER TABLE `blockchains` 
     MODIFY COLUMN `BlockchainID` INT NOT NULL AUTO_INCREMENT,
     COMMENT = ''جدول بلاکچین‌های پشتیبانی شده'';',
    'SELECT ''Table blockchains does not exist'' as warning;'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 6. اصلاح جدول address (اگر وجود داشته باشد)
-- Fix address table (if exists)
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'address') > 0,
    'ALTER TABLE `address` 
     MODIFY COLUMN `AddressID` INT NOT NULL AUTO_INCREMENT,
     MODIFY COLUMN `PrivateKey` TEXT DEFAULT NULL COMMENT ''کلید خصوصی (رمزگذاری شده)'',
     MODIFY COLUMN `PhraseKey` TEXT DEFAULT NULL COMMENT ''عبارت بازیابی (رمزگذاری شده)'',
     COMMENT = ''جدول آدرس‌های کیف پول‌ها'';',
    'SELECT ''Table address does not exist'' as warning;'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 7. اصلاح جدول prices (اگر وجود داشته باشد)
-- Fix prices table (if exists)
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'prices') > 0,
    'ALTER TABLE `prices` 
     MODIFY COLUMN `is_historical` ENUM(''0'', ''1'') NOT NULL DEFAULT ''0'' COMMENT ''0=قیمت فعلی, 1=قیمت تاریخی'',
     COMMENT = ''جدول قیمت‌های ارزها'';',
    'SELECT ''Table prices does not exist'' as warning;'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 8. اصلاح جدول transfers (اگر وجود داشته باشد)
-- Fix transfers table (if exists)
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'transfers') > 0,
    'ALTER TABLE `transfers` 
     MODIFY COLUMN `Direction` ENUM(''inbound'', ''outbound'') NOT NULL COMMENT ''نوع انتقال: دریافتی یا ارسالی'',
     MODIFY COLUMN `Status` ENUM(''pending'', ''confirmed'', ''failed'') DEFAULT ''pending'' COMMENT ''وضعیت تراکنش'',
     MODIFY COLUMN `AssetType` ENUM(''native'', ''token'') DEFAULT ''native'' COMMENT ''نوع دارایی'',
     MODIFY COLUMN `IsSuccessful` ENUM(''0'', ''1'') NOT NULL DEFAULT ''1'' COMMENT ''0=ناموفق, 1=موفق'',
     COMMENT = ''جدول تراکنش‌های انتقال'';',
    'SELECT ''Table transfers does not exist'' as warning;'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 9. اصلاح جدول user_devices (اگر وجود داشته باشد)
-- Fix user_devices table (if exists)
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user_devices') > 0,
    'ALTER TABLE `user_devices` 
     MODIFY COLUMN `DeviceID` INT NOT NULL AUTO_INCREMENT,
     MODIFY COLUMN `DeviceType` ENUM(''android'', ''ios'', ''web'', ''desktop'') DEFAULT NULL COMMENT ''نوع دستگاه'',
     COMMENT = ''جدول دستگاه‌های کاربران'';',
    'SELECT ''Table user_devices does not exist'' as warning;'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 10. اصلاح جدول balance_update_log (اگر وجود داشته باشد)
-- Fix balance_update_log table (if exists)
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'balance_update_log') > 0,
    'ALTER TABLE `balance_update_log`
     MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT,
     MODIFY COLUMN `direction` ENUM(''inbound'', ''outbound'') NOT NULL COMMENT ''نوع تراکنش: دریافتی یا ارسالی'',
     COMMENT = ''لاگ به‌روزرسانی موجودی'';',
    'SELECT ''Table balance_update_log does not exist'' as warning;'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- نمایش جداول موجود بعد از اصلاح
SELECT 'UI fixes applied successfully to existing tables!' as Status;

-- نمایش جداول موجود
SELECT 
    TABLE_NAME as 'Table Name',
    TABLE_COMMENT as 'Comment',
    TABLE_ROWS as 'Rows'
FROM 
    INFORMATION_SCHEMA.TABLES 
WHERE 
    TABLE_SCHEMA = DATABASE()
ORDER BY 
    TABLE_NAME;
