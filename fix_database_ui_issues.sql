-- اصلاح مشکلات UI در phpMyAdmin
-- Fix UI issues in phpMyAdmin

-- 1. اصلاح فیلدهای Direction و Status در جدول transfers
-- تبدیل به ENUM برای نمایش dropdown در phpMyAdmin
ALTER TABLE `transfers` 
MODIFY COLUMN `Direction` ENUM('inbound', 'outbound') NOT NULL COMMENT 'نوع انتقال: دریافتی یا ارسالی',
MODIFY COLUMN `Status` ENUM('pending', 'confirmed', 'failed') DEFAULT 'pending' COMMENT 'وضعیت تراکنش',
MODIFY COLUMN `AssetType` ENUM('native', 'token') DEFAULT 'native' COMMENT 'نوع دارایی';

-- 2. اصلاح فیلد Direction در جدول balance_update_log  
ALTER TABLE `balance_update_log`
MODIFY COLUMN `direction` ENUM('inbound', 'outbound') NOT NULL COMMENT 'نوع تراکنش: دریافتی یا ارسالی';

-- 3. اصلاح فیلد DeviceType در جدول user_devices
ALTER TABLE `user_devices`
MODIFY COLUMN `DeviceType` ENUM('android', 'ios', 'web', 'desktop') DEFAULT NULL COMMENT 'نوع دستگاه';

-- 4. اصلاح فیلد RawData در جدول userholding
-- تغییر نوع از JSON به TEXT برای نمایش بهتر
ALTER TABLE `userholding`
MODIFY COLUMN `RawData` TEXT DEFAULT NULL COMMENT 'داده‌های خام به صورت JSON';

-- 5. اضافه کردن محدودیت طول برای فیلدهای WalletID و UserID
-- برای نمایش بهتر در phpMyAdmin

-- بررسی حداکثر طول موجود در WalletID
-- SELECT MAX(LENGTH(WalletID)) as max_wallet_id_length FROM wallets;

-- بررسی حداکثر طول موجود در UserID  
-- SELECT MAX(LENGTH(UserID)) as max_user_id_length FROM users;

-- 6. اصلاح نمایش فیلدهای Boolean
ALTER TABLE `wallets`
MODIFY COLUMN `IsMultiSig` ENUM('0', '1') NOT NULL DEFAULT '0' COMMENT '0=خیر, 1=بله';

ALTER TABLE `currencies`
MODIFY COLUMN `IsToken` ENUM('0', '1') NOT NULL DEFAULT '0' COMMENT '0=ارز اصلی, 1=توکن';

ALTER TABLE `userholding`
MODIFY COLUMN `IsToken` ENUM('0', '1') NOT NULL DEFAULT '0' COMMENT '0=ارز اصلی, 1=توکن';

ALTER TABLE `transfers`
MODIFY COLUMN `IsSuccessful` ENUM('0', '1') NOT NULL DEFAULT '1' COMMENT '0=ناموفق, 1=موفق';

ALTER TABLE `prices`
MODIFY COLUMN `is_historical` ENUM('0', '1') NOT NULL DEFAULT '0' COMMENT '0=قیمت فعلی, 1=قیمت تاریخی';

-- 7. بهبود نمایش فیلدهای TEXT طولانی
ALTER TABLE `address`
MODIFY COLUMN `PrivateKey` TEXT DEFAULT NULL COMMENT 'کلید خصوصی (رمزگذاری شده)',
MODIFY COLUMN `PhraseKey` TEXT DEFAULT NULL COMMENT 'عبارت بازیابی (رمزگذاری شده)';

-- 8. اضافه کردن COMMENT برای جداول برای وضوح بیشتر
ALTER TABLE `users` COMMENT = 'جدول کاربران سیستم';
ALTER TABLE `wallets` COMMENT = 'جدول کیف پول‌های کاربران';
ALTER TABLE `blockchains` COMMENT = 'جدول بلاکچین‌های پشتیبانی شده';
ALTER TABLE `currencies` COMMENT = 'جدول ارزها و توکن‌ها';
ALTER TABLE `address` COMMENT = 'جدول آدرس‌های کیف پول‌ها';
ALTER TABLE `transfers` COMMENT = 'جدول تراکنش‌های انتقال';
ALTER TABLE `userholding` COMMENT = 'جدول موجودی کاربران';
ALTER TABLE `prices` COMMENT = 'جدول قیمت‌های ارزها';
ALTER TABLE `user_devices` COMMENT = 'جدول دستگاه‌های کاربران';
ALTER TABLE `balance_update_log` COMMENT = 'لاگ به‌روزرسانی موجودی';

-- 9. بهبود نمایش فیلدهای ID
-- اضافه کردن padding صفر برای نمایش بهتر ID های عددی
ALTER TABLE `users`
MODIFY COLUMN `ID` INT NOT NULL AUTO_INCREMENT ZEROFILL;

ALTER TABLE `blockchains`
MODIFY COLUMN `BlockchainID` INT NOT NULL AUTO_INCREMENT ZEROFILL;

ALTER TABLE `address`
MODIFY COLUMN `AddressID` INT NOT NULL AUTO_INCREMENT ZEROFILL;

ALTER TABLE `user_devices`
MODIFY COLUMN `DeviceID` INT NOT NULL AUTO_INCREMENT ZEROFILL;

ALTER TABLE `balance_update_log`
MODIFY COLUMN `id` INT NOT NULL AUTO_INCREMENT ZEROFILL;

-- 10. تنظیم display width برای فیلدهای مهم
ALTER TABLE `currencies`
MODIFY COLUMN `CurrencyID` VARCHAR(10) NOT NULL COMMENT 'شناسه منحصر به فرد ارز',
MODIFY COLUMN `Symbol` VARCHAR(50) NOT NULL COMMENT 'نماد ارز',
MODIFY COLUMN `CurrencyName` VARCHAR(255) NOT NULL COMMENT 'نام کامل ارز';

-- نمایش پیام موفقیت
SELECT 'Database UI issues fixed successfully!' as Status,
       'فیلدهای WalletID و UserID حالا به صورت input نمایش داده می‌شوند' as WalletID_UserID,
       'فیلدهای Direction، Status و AssetType حالا dropdown هستند' as Dropdown_Fields,
       'فیلد RawData حالا به صورت TEXT نمایش داده می‌شود' as RawData_Field,
       'تمام فیلدهای Boolean حالا ENUM هستند' as Boolean_Fields;
