-- ============================================================
-- Migration: Add dedicated price_alerts table
-- ============================================================
-- این میگریشن یک جدول اختصاصی برای price alerts ایجاد می‌کند
-- که جایگزین روش قدیمی ذخیره‌سازی در جدول settings می‌شود.
--
-- مزایا:
-- 1. پشتیبانی از هشدار درصدی (percent_up / percent_down)
-- 2. عملکرد بهتر با ایندکس‌های اختصاصی
-- 3. امکان ذخیره reference_price برای هشدارهای درصدی
-- 4. backward compatible — داده‌های قدیمی در settings باقی می‌مانند
-- ============================================================

CREATE TABLE IF NOT EXISTS price_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    symbol VARCHAR(10) NOT NULL,

    -- Type: above | below | percent_up | percent_down
    alert_type VARCHAR(20) NOT NULL,

    -- For custom price alerts (above/below)
    target_price DECIMAL(20, 8) NULL,

    -- For percentage alerts (percent_up/percent_down)
    target_percent DECIMAL(10, 2) NULL,
    reference_price DECIMAL(20, 8) NULL,

    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_price_alerts_user (user_id),
    INDEX idx_price_alerts_symbol (symbol),
    INDEX idx_price_alerts_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Optionally migrate existing settings-based alerts
-- Note: settings-based alerts use key format:
--   price_alert:{user_id}:{symbol}:{alert_type}
-- This is run manually if needed; the old data remains readable
-- for backward compatibility.
-- ============================================================
-- INSERT IGNORE INTO price_alerts (user_id, symbol, alert_type, target_price, is_active)
-- SELECT
--     SUBSTRING_INDEX(SUBSTRING_INDEX(setting_key, ':', 2), ':', -1) AS user_id,
--     SUBSTRING_INDEX(SUBSTRING_INDEX(setting_key, ':', 3), ':', -1) AS symbol,
--     SUBSTRING_INDEX(setting_key, ':', -1) AS alert_type,
--     CAST(setting_value AS DECIMAL(20, 8)) AS target_price,
--     1 AS is_active
-- FROM settings
-- WHERE setting_key LIKE 'price_alert:%';
