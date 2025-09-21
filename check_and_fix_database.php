<?php
/**
 * بررسی و اصلاح دیتابیس - نسخه ایمن
 * Check and Fix Database - Safe Version
 */

// تنظیمات اتصال به دیتابیس
$host = '127.0.0.1';
$username = 'coincee';
$password = 'your_password_here'; // باید از فایل .env خوانده شود
$database = 'coincee';

try {
    // اتصال به دیتابیس
    $pdo = new PDO("mysql:host=$host;dbname=$database;charset=utf8mb4", $username, $password);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    
    echo "🔗 اتصال به دیتابیس برقرار شد\n";
    
    // بررسی جداول موجود
    echo "\n📋 بررسی جداول موجود...\n";
    echo str_repeat("=", 50) . "\n";
    
    $stmt = $pdo->query("SHOW TABLES");
    $tables = $stmt->fetchAll(PDO::FETCH_COLUMN);
    
    echo "📊 جداول موجود در دیتابیس:\n";
    foreach ($tables as $table) {
        echo "  ✓ $table\n";
    }
    
    // لیست جداول مورد انتظار
    $expectedTables = [
        'users', 'wallets', 'blockchains', 'currencies', 'address', 
        'transfers', 'userholding', 'prices', 'user_devices', 'balance_update_log'
    ];
    
    $existingTables = array_intersect($expectedTables, $tables);
    $missingTables = array_diff($expectedTables, $tables);
    
    echo "\n📈 آمار جداول:\n";
    echo "  ✅ موجود: " . count($existingTables) . " جدول\n";
    echo "  ❌ مفقود: " . count($missingTables) . " جدول\n";
    
    if (!empty($missingTables)) {
        echo "\n⚠️ جداول مفقود:\n";
        foreach ($missingTables as $table) {
            echo "  ❌ $table\n";
        }
    }
    
    // اگر هیچ جدولی وجود ندارد، ابتدا جداول را ایجاد کن
    if (empty($existingTables)) {
        echo "\n🚨 هیچ جدولی وجود ندارد! ابتدا جداول را ایجاد کنید:\n";
        echo "   php -f create_database_tables.sql\n";
        echo "   یا از phpMyAdmin فایل create_database_tables.sql را اجرا کنید\n";
        return;
    }
    
    // اعمال اصلاحات UI روی جداول موجود
    echo "\n🔧 اعمال اصلاحات UI...\n";
    echo str_repeat("=", 50) . "\n";
    
    // خواندن فایل SQL ایمن
    $sqlFile = 'fix_database_ui_issues_safe.sql';
    if (!file_exists($sqlFile)) {
        throw new Exception("فایل SQL پیدا نشد: $sqlFile");
    }
    
    $sql = file_get_contents($sqlFile);
    
    // اجرای SQL
    try {
        $pdo->exec($sql);
        echo "✅ اصلاحات UI با موفقیت اعمال شد!\n";
    } catch (PDOException $e) {
        echo "⚠️ برخی اصلاحات ممکن است اعمال نشده باشند: " . $e->getMessage() . "\n";
    }
    
    // بررسی نهایی و نمایش نتایج
    echo "\n📊 بررسی نهایی...\n";
    echo str_repeat("=", 50) . "\n";
    
    // بررسی فیلدهای اصلاح شده
    $checksToPerform = [
        ['userholding', 'IsToken', 'enum'],
        ['userholding', 'RawData', 'text'],
        ['wallets', 'IsMultiSig', 'enum'],
        ['currencies', 'IsToken', 'enum'],
        ['prices', 'is_historical', 'enum']
    ];
    
    foreach ($checksToPerform as $check) {
        list($table, $column, $expectedType) = $check;
        
        if (in_array($table, $existingTables)) {
            try {
                $stmt = $pdo->query("DESCRIBE `$table` `$column`");
                $columnInfo = $stmt->fetch(PDO::FETCH_ASSOC);
                
                if ($columnInfo) {
                    $actualType = strtolower($columnInfo['Type']);
                    if (strpos($actualType, $expectedType) !== false) {
                        echo "  ✅ $table.$column: اصلاح شد ($actualType)\n";
                    } else {
                        echo "  ⚠️ $table.$column: نیاز به بررسی ($actualType)\n";
                    }
                } else {
                    echo "  ❓ $table.$column: فیلد پیدا نشد\n";
                }
            } catch (PDOException $e) {
                echo "  ❌ $table.$column: خطا در بررسی\n";
            }
        }
    }
    
    echo "\n🎉 فرآیند تکمیل شد!\n";
    echo "\n📋 مراحل بعدی:\n";
    echo "1. phpMyAdmin را refresh کنید\n";
    echo "2. جداول را بررسی کنید:\n";
    foreach ($existingTables as $table) {
        echo "   - $table: فیلدها باید dropdown/input مناسب داشته باشند\n";
    }
    
    if (!empty($missingTables)) {
        echo "\n⚠️ برای جداول مفقود:\n";
        echo "   ابتدا create_database_tables.sql را اجرا کنید\n";
        echo "   سپس این اسکریپت را دوباره اجرا کنید\n";
    }
    
} catch (PDOException $e) {
    echo "❌ خطا در اتصال به دیتابیس: " . $e->getMessage() . "\n";
    echo "\n💡 راه حل‌های محتمل:\n";
    echo "1. بررسی تنظیمات اتصال (host, username, password, database)\n";
    echo "2. اطمینان از در دسترس بودن MySQL server\n";
    echo "3. بررسی دسترسی‌های کاربر به دیتابیس\n";
} catch (Exception $e) {
    echo "❌ خطا: " . $e->getMessage() . "\n";
}
?>

