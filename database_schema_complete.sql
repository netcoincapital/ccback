-- کوئری‌های MySQL کامل برای ساخت دیتابیس Coinceeper
-- بر اساس ساختار SQLAlchemy models و داده‌های موجود

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

-- حذف جدول‌ها در صورت وجود (به ترتیب وابستگی)
DROP TABLE IF EXISTS `balance_update_log`;
DROP TABLE IF EXISTS `user_devices`;
DROP TABLE IF EXISTS `transfers`;
DROP TABLE IF EXISTS `userholding`;
DROP TABLE IF EXISTS `prices`;
DROP TABLE IF EXISTS `address`;
DROP TABLE IF EXISTS `currencies`;
DROP TABLE IF EXISTS `wallets`;
DROP TABLE IF EXISTS `blockchains`;
DROP TABLE IF EXISTS `users`;

-- ایجاد جدول users
CREATE TABLE `users` (
    `UserID` VARCHAR(36) NOT NULL,
    `ID` INT NOT NULL AUTO_INCREMENT,
    `Email` VARCHAR(255) UNIQUE DEFAULT NULL,
    `Device` VARCHAR(255) DEFAULT NULL,
    `IP` VARCHAR(45) DEFAULT NULL,
    `CreatedAt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `UpdatedAt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`UserID`),
    UNIQUE KEY `idx_id` (`ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ایجاد جدول blockchains
CREATE TABLE `blockchains` (
    `BlockchainID` INT NOT NULL AUTO_INCREMENT,
    `BlockchainName` VARCHAR(100) NOT NULL UNIQUE,
    `Symbol` VARCHAR(50) NOT NULL,
    `ChainCode` VARCHAR(100) NOT NULL,
    `CreatedAt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `UpdatedAt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`BlockchainID`),
    UNIQUE KEY `idx_blockchain_name` (`BlockchainName`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ایجاد جدول wallets
CREATE TABLE `wallets` (
    `WalletID` VARCHAR(50) NOT NULL,
    `UserID` VARCHAR(36) NOT NULL,
    `IsMultiSig` BOOLEAN NOT NULL DEFAULT FALSE,
    `RequiredSignatures` VARCHAR(10) NOT NULL,
    `CreatedAt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `UpdatedAt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`WalletID`),
    FOREIGN KEY (`UserID`) REFERENCES `users`(`UserID`) ON DELETE CASCADE,
    KEY `idx_user_id` (`UserID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ایجاد جدول currencies با ساختار دقیق بر اساس فایل موجود
CREATE TABLE `currencies` (
    `CurrencyID` VARCHAR(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `CurrencyName` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `cmc_id` INT DEFAULT NULL,
    `Symbol` VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `BlockchainID` INT NOT NULL,
    `DecimalPlaces` INT NOT NULL,
    `IsToken` TINYINT(1) DEFAULT '0',
    `SmartContractAddress` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `CreatedAt` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    `UpdatedAt` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `Icon` VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    PRIMARY KEY (`CurrencyID`),
    KEY `BlockchainID` (`BlockchainID`),
    CONSTRAINT `currencies_ibfk_1` FOREIGN KEY (`BlockchainID`) REFERENCES `blockchains` (`BlockchainID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ایجاد جدول address
CREATE TABLE `address` (
    `AddressID` INT NOT NULL AUTO_INCREMENT,
    `WalletID` VARCHAR(50) NOT NULL,
    `BlockchainID` INT NOT NULL,
    `PublicAddress` VARCHAR(255) NOT NULL,
    `PrivateKey` TEXT DEFAULT NULL,
    `PhraseKey` TEXT DEFAULT NULL,
    `CreatedAt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `UpdatedAt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`AddressID`),
    FOREIGN KEY (`WalletID`) REFERENCES `wallets`(`WalletID`) ON DELETE CASCADE,
    FOREIGN KEY (`BlockchainID`) REFERENCES `blockchains`(`BlockchainID`),
    KEY `ix_public_address` (`PublicAddress`),
    KEY `idx_wallet_id` (`WalletID`),
    KEY `idx_blockchain_id` (`BlockchainID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ایجاد جدول transfers
CREATE TABLE `transfers` (
    `TransferID` BIGINT NOT NULL AUTO_INCREMENT,
    `BlockchainID` INT NOT NULL,
    `AddressID` INT NOT NULL,
    `WalletID` VARCHAR(50) NOT NULL,
    `TxHash` VARCHAR(100) NOT NULL,
    `BlockNumber` BIGINT DEFAULT NULL,
    `Timestamp` TIMESTAMP DEFAULT NULL,
    `FromAddress` VARCHAR(100) DEFAULT NULL,
    `ToAddress` VARCHAR(100) DEFAULT NULL,
    `Amount` DECIMAL(38,18) NOT NULL DEFAULT 0,
    `Price` DECIMAL(38,18) DEFAULT NULL,
    `TokenSymbol` VARCHAR(20) DEFAULT NULL,
    `TokenContract` VARCHAR(100) DEFAULT NULL,
    `AssetType` VARCHAR(20) DEFAULT NULL COMMENT 'native / token',
    `Fee` DECIMAL(38,18) DEFAULT 0,
    `Direction` VARCHAR(10) NOT NULL COMMENT 'inbound / outbound',
    `Status` VARCHAR(20) DEFAULT NULL COMMENT 'pending / confirmed / failed',
    `IsSuccessful` BOOLEAN NOT NULL DEFAULT TRUE,
    `ExplorerUrl` TEXT DEFAULT NULL,
    `CreatedAt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `UpdatedAt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`TransferID`),
    FOREIGN KEY (`BlockchainID`) REFERENCES `blockchains`(`BlockchainID`),
    FOREIGN KEY (`AddressID`) REFERENCES `address`(`AddressID`),
    FOREIGN KEY (`WalletID`) REFERENCES `wallets`(`WalletID`),
    KEY `idx_tx_hash` (`TxHash`),
    KEY `idx_blockchain_id` (`BlockchainID`),
    KEY `idx_address_id` (`AddressID`),
    KEY `idx_wallet_id` (`WalletID`),
    KEY `idx_direction` (`Direction`),
    KEY `idx_timestamp` (`Timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ایجاد جدول userholding
CREATE TABLE `userholding` (
    `HoldingID` BIGINT NOT NULL AUTO_INCREMENT,
    `UserID` VARCHAR(36) NOT NULL,
    `CurrencyID` VARCHAR(10) NOT NULL,
    `Balance` DECIMAL(38,18) NOT NULL DEFAULT 0,
    `Symbol` VARCHAR(20) NOT NULL,
    `Blockchain` VARCHAR(50) NOT NULL,
    `IsToken` BOOLEAN NOT NULL DEFAULT FALSE,
    `LastUpdated` TIMESTAMP DEFAULT NULL,
    `RawData` JSON DEFAULT NULL,
    `CreatedAt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `UpdatedAt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`HoldingID`),
    FOREIGN KEY (`UserID`) REFERENCES `users`(`UserID`) ON DELETE CASCADE,
    FOREIGN KEY (`CurrencyID`) REFERENCES `currencies`(`CurrencyID`),
    KEY `idx_user_id` (`UserID`),
    KEY `idx_currency_id` (`CurrencyID`),
    KEY `idx_symbol` (`Symbol`),
    KEY `idx_blockchain` (`Blockchain`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ایجاد جدول prices
CREATE TABLE `prices` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `crypto_id` VARCHAR(10) NOT NULL,
    `currency` VARCHAR(10) NOT NULL DEFAULT 'USD',
    `price` DECIMAL(20,8) NOT NULL,
    `market_cap` DECIMAL(30,2) DEFAULT NULL,
    `volume_24h` DECIMAL(30,2) DEFAULT NULL,
    `change_1h` DECIMAL(8,2) DEFAULT NULL,
    `change_24h` DECIMAL(8,2) DEFAULT NULL,
    `change_7d` DECIMAL(8,2) DEFAULT NULL,
    `is_historical` BOOLEAN NOT NULL DEFAULT FALSE,
    `timestamp` DATETIME DEFAULT NULL,
    `last_updated` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    FOREIGN KEY (`crypto_id`) REFERENCES `currencies`(`CurrencyID`),
    UNIQUE KEY `unique_crypto_currency_timestamp` (`crypto_id`, `currency`, `timestamp`),
    KEY `crypto_id_idx` (`crypto_id`),
    KEY `timestamp_idx` (`timestamp`),
    KEY `historical_idx` (`is_historical`),
    KEY `current_price_idx` (`crypto_id`, `currency`, `is_historical`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ایجاد جدول user_devices
CREATE TABLE `user_devices` (
    `DeviceID` INT NOT NULL AUTO_INCREMENT,
    `UserID` VARCHAR(36) NOT NULL,
    `WalletID` VARCHAR(50) NOT NULL,
    `DeviceToken` VARCHAR(500) NOT NULL UNIQUE,
    `DeviceName` VARCHAR(100) DEFAULT NULL,
    `DeviceType` VARCHAR(50) DEFAULT NULL COMMENT 'android, ios',
    `CreatedAt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `UpdatedAt` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`DeviceID`),
    FOREIGN KEY (`UserID`) REFERENCES `users`(`UserID`) ON DELETE CASCADE,
    FOREIGN KEY (`WalletID`) REFERENCES `wallets`(`WalletID`) ON DELETE CASCADE,
    UNIQUE KEY `idx_device_token` (`DeviceToken`),
    KEY `idx_user_id` (`UserID`),
    KEY `idx_wallet_id` (`WalletID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ایجاد جدول balance_update_log
CREATE TABLE `balance_update_log` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `wallet_id` VARCHAR(50) NOT NULL,
    `tx_id` VARCHAR(255) NOT NULL,
    `direction` VARCHAR(20) NOT NULL COMMENT 'inbound یا outbound',
    `amount` VARCHAR(50) NOT NULL,
    `token_symbol` VARCHAR(50) NOT NULL,
    `blockchain` VARCHAR(50) NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_wallet_tx_direction` (`wallet_id`, `tx_id`, `direction`),
    KEY `idx_wallet_id` (`wallet_id`),
    KEY `idx_tx_id` (`tx_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- اضافه کردن داده‌های پایه برای blockchains
INSERT INTO `blockchains` (`BlockchainName`, `Symbol`, `ChainCode`) VALUES
('Ethereum', 'ETH', 'ethereum'),
('Tron', 'TRX', 'tron'),
('Binance Smart Chain', 'BNB', 'bsc'),
('Bitcoin', 'BTC', 'bitcoin'),
('Polygon', 'MATIC', 'polygon'),
('Avalanche', 'AVAX', 'avalanche'),
('Arbitrum', 'ARB', 'arbitrum'),
('Solana', 'SOL', 'solana'),
('XRP', 'XRP', 'xrp'),
('Polkadot', 'DOT', 'polkadot');

-- برای اضافه کردن تمام currencies، فایل currencies_complete.sql را اجرا کنید
-- SOURCE currencies_complete.sql;

COMMIT;
SELECT 'Database schema created successfully! Run currencies_complete.sql to populate currencies.' as Status;
