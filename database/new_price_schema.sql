-- ========================================
-- New Price System Schema - Production Grade
-- Based on Industry Standards (Exchanges, Trading Platforms)
-- ========================================

-- 1. Fiat Exchange Rates Table
-- Store exchange rates for converting USD to other fiats
CREATE TABLE IF NOT EXISTS fiat_rates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    base_currency VARCHAR(10) NOT NULL DEFAULT 'USD',
    quote_currency VARCHAR(10) NOT NULL,
    rate DECIMAL(20, 8) NOT NULL,
    last_updated DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_pair (base_currency, quote_currency),
    INDEX idx_quote (quote_currency),
    INDEX idx_updated (last_updated)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert common fiat rates (will be updated by cron)
INSERT INTO fiat_rates (base_currency, quote_currency, rate) VALUES
('USD', 'USD', 1.00000000),
('USD', 'EUR', 0.92000000),
('USD', 'GBP', 0.79000000),
('USD', 'JPY', 149.50000000),
('USD', 'CNY', 7.24000000),
('USD', 'KRW', 1320.00000000),
('USD', 'RUB', 92.00000000),
('USD', 'TRY', 32.50000000),
('USD', 'INR', 83.20000000),
('USD', 'BRL', 5.00000000),
('USD', 'AUD', 1.53000000),
('USD', 'CAD', 1.37000000),
('USD', 'CHF', 0.88000000),
('USD', 'MXN', 17.00000000),
('USD', 'AED', 3.67000000),
('USD', 'IRR', 42000.00000000)
ON DUPLICATE KEY UPDATE rate=VALUES(rate), last_updated=CURRENT_TIMESTAMP;

-- 2. Symbols Reference Table (replaces currencies table)
CREATE TABLE IF NOT EXISTS symbols (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    cmc_id VARCHAR(20),
    coingecko_id VARCHAR(100),
    is_active TINYINT(1) DEFAULT 1,
    market_cap_rank INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_symbol (symbol),
    INDEX idx_cmc_id (cmc_id),
    INDEX idx_active (is_active),
    INDEX idx_rank (market_cap_rank)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Raw Ticks (Recent Data - High Resolution)
-- Stores recent price ticks (last 7-30 days)
-- All prices in USD only
CREATE TABLE IF NOT EXISTS ticks_recent (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol_id INT NOT NULL,
    price DECIMAL(30, 10) NOT NULL,
    volume_24h DECIMAL(30, 2),
    market_cap DECIMAL(30, 2),
    timestamp DATETIME(3) NOT NULL,
    INDEX idx_symbol_time (symbol_id, timestamp),
    INDEX idx_timestamp (timestamp),
    FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
PARTITION BY RANGE (TO_DAYS(timestamp)) (
    PARTITION p_old VALUES LESS THAN (TO_DAYS('2025-11-01')),
    PARTITION p_2025_11_01 VALUES LESS THAN (TO_DAYS('2025-11-02')),
    PARTITION p_2025_11_02 VALUES LESS THAN (TO_DAYS('2025-11-03')),
    PARTITION p_2025_11_03 VALUES LESS THAN (TO_DAYS('2025-11-04')),
    PARTITION p_2025_11_04 VALUES LESS THAN (TO_DAYS('2025-11-05')),
    PARTITION p_2025_11_05 VALUES LESS THAN (TO_DAYS('2025-11-06')),
    PARTITION p_2025_11_06 VALUES LESS THAN (TO_DAYS('2025-11-07')),
    PARTITION p_2025_11_07 VALUES LESS THAN (TO_DAYS('2025-11-08')),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);

-- 4. Candles - 1 Minute (for 1h, 1d charts)
CREATE TABLE IF NOT EXISTS candles_1m (
    id BIGINT AUTO_INCREMENT,
    symbol_id INT NOT NULL,
    open_price DECIMAL(30, 10) NOT NULL,
    high_price DECIMAL(30, 10) NOT NULL,
    low_price DECIMAL(30, 10) NOT NULL,
    close_price DECIMAL(30, 10) NOT NULL,
    volume DECIMAL(30, 2),
    timestamp DATETIME NOT NULL,
    PRIMARY KEY (id, timestamp),
    UNIQUE KEY unique_symbol_time (symbol_id, timestamp),
    INDEX idx_timestamp (timestamp),
    FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
PARTITION BY RANGE (TO_DAYS(timestamp)) (
    PARTITION p_old VALUES LESS THAN (TO_DAYS('2025-10-01')),
    PARTITION p_2025_10 VALUES LESS THAN (TO_DAYS('2025-11-01')),
    PARTITION p_2025_11 VALUES LESS THAN (TO_DAYS('2025-12-01')),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);

-- 5. Candles - 1 Hour (for 1w, 1m charts)
CREATE TABLE IF NOT EXISTS candles_1h (
    id BIGINT AUTO_INCREMENT,
    symbol_id INT NOT NULL,
    open_price DECIMAL(30, 10) NOT NULL,
    high_price DECIMAL(30, 10) NOT NULL,
    low_price DECIMAL(30, 10) NOT NULL,
    close_price DECIMAL(30, 10) NOT NULL,
    volume DECIMAL(30, 2),
    timestamp DATETIME NOT NULL,
    PRIMARY KEY (id, timestamp),
    UNIQUE KEY unique_symbol_time (symbol_id, timestamp),
    INDEX idx_timestamp (timestamp),
    FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
PARTITION BY RANGE (YEAR(timestamp) * 100 + MONTH(timestamp)) (
    PARTITION p_202410 VALUES LESS THAN (202411),
    PARTITION p_202411 VALUES LESS THAN (202412),
    PARTITION p_202412 VALUES LESS THAN (202501),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);

-- 6. Candles - 1 Day (for 1y, All charts)
CREATE TABLE IF NOT EXISTS candles_1d (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol_id INT NOT NULL,
    open_price DECIMAL(30, 10) NOT NULL,
    high_price DECIMAL(30, 10) NOT NULL,
    low_price DECIMAL(30, 10) NOT NULL,
    close_price DECIMAL(30, 10) NOT NULL,
    volume DECIMAL(30, 2),
    market_cap DECIMAL(30, 2),
    timestamp DATE NOT NULL,
    UNIQUE KEY unique_symbol_time (symbol_id, timestamp),
    INDEX idx_timestamp (timestamp),
    FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Current Prices (Fast Lookup - Updated Frequently)
CREATE TABLE IF NOT EXISTS current_prices (
    symbol_id INT PRIMARY KEY,
    price DECIMAL(30, 10) NOT NULL,
    volume_24h DECIMAL(30, 2),
    market_cap DECIMAL(30, 2),
    change_1h DECIMAL(10, 4),
    change_24h DECIMAL(10, 4),
    change_7d DECIMAL(10, 4),
    last_updated DATETIME(3) NOT NULL,
    FOREIGN KEY (symbol_id) REFERENCES symbols(id) ON DELETE CASCADE,
    INDEX idx_updated (last_updated)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ========================================
-- Views for Easy Querying
-- ========================================

-- View: Current prices with symbol names
CREATE OR REPLACE VIEW v_current_prices AS
SELECT 
    s.id,
    s.symbol,
    s.name,
    cp.price,
    cp.volume_24h,
    cp.market_cap,
    cp.change_1h,
    cp.change_24h,
    cp.change_7d,
    cp.last_updated
FROM symbols s
INNER JOIN current_prices cp ON s.id = cp.symbol_id
WHERE s.is_active = 1;

-- ========================================
-- Stored Procedures
-- ========================================

DELIMITER //

-- Get price in any fiat currency
CREATE PROCEDURE sp_get_price_in_fiat(
    IN p_symbol_id INT,
    IN p_fiat_currency VARCHAR(10)
)
BEGIN
    SELECT 
        s.symbol,
        s.name,
        cp.price AS price_usd,
        cp.price * COALESCE(fr.rate, 1) AS price_fiat,
        p_fiat_currency AS currency,
        cp.volume_24h,
        cp.market_cap,
        cp.change_1h,
        cp.change_24h,
        cp.change_7d,
        cp.last_updated
    FROM symbols s
    INNER JOIN current_prices cp ON s.id = cp.symbol_id
    LEFT JOIN fiat_rates fr ON fr.quote_currency = p_fiat_currency
    WHERE s.id = p_symbol_id;
END //

-- Get candles for chart
CREATE PROCEDURE sp_get_candles(
    IN p_symbol_id INT,
    IN p_interval VARCHAR(10),
    IN p_start_time DATETIME,
    IN p_end_time DATETIME
)
BEGIN
    IF p_interval = '1m' THEN
        SELECT * FROM candles_1m 
        WHERE symbol_id = p_symbol_id 
          AND timestamp BETWEEN p_start_time AND p_end_time
        ORDER BY timestamp;
    ELSEIF p_interval = '1h' THEN
        SELECT * FROM candles_1h 
        WHERE symbol_id = p_symbol_id 
          AND timestamp BETWEEN p_start_time AND p_end_time
        ORDER BY timestamp;
    ELSEIF p_interval = '1d' THEN
        SELECT * FROM candles_1d 
        WHERE symbol_id = p_symbol_id 
          AND timestamp BETWEEN p_start_time AND p_end_time
        ORDER BY timestamp;
    END IF;
END //

DELIMITER ;

-- ========================================
-- Benefits of This Schema:
-- ========================================
-- 1. Store prices in USD only (16x less data)
-- 2. Convert to fiat on-the-fly using fiat_rates
-- 3. Partitioned tables for easy maintenance (DROP old partitions)
-- 4. Separate candle tables for different resolutions
-- 5. current_prices table for fast lookups
-- 6. No duplicate data
-- 7. Standard industry pattern
-- ========================================

