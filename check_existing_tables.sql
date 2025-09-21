-- بررسی جداول موجود در دیتابیس
-- Check existing tables in database

-- نمایش همه جداول موجود
SHOW TABLES;

-- نمایش ساختار جداول موجود
SELECT 
    TABLE_NAME,
    TABLE_COMMENT,
    TABLE_ROWS,
    CREATE_TIME
FROM 
    INFORMATION_SCHEMA.TABLES 
WHERE 
    TABLE_SCHEMA = 'coincee'
ORDER BY 
    TABLE_NAME;

-- بررسی وجود جداول مورد نظر
SELECT 
    CASE 
        WHEN EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'coincee' AND TABLE_NAME = 'transfers') 
        THEN 'EXISTS' 
        ELSE 'NOT EXISTS' 
    END AS transfers_status,
    CASE 
        WHEN EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'coincee' AND TABLE_NAME = 'userholding') 
        THEN 'EXISTS' 
        ELSE 'NOT EXISTS' 
    END AS userholding_status,
    CASE 
        WHEN EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'coincee' AND TABLE_NAME = 'balance_update_log') 
        THEN 'EXISTS' 
        ELSE 'NOT EXISTS' 
    END AS balance_update_log_status,
    CASE 
        WHEN EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'coincee' AND TABLE_NAME = 'user_devices') 
        THEN 'EXISTS' 
        ELSE 'NOT EXISTS' 
    END AS user_devices_status;

