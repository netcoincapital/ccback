-- phpMyAdmin SQL Dump
-- version 5.2.2-1.el9
-- https://www.phpmyadmin.net/
--
-- Host: localhost
-- Generation Time: May 10, 2025 at 10:09 AM
-- Server version: 8.0.36
-- PHP Version: 8.0.30

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `coincee`
--

-- --------------------------------------------------------

--
-- Table structure for table `currencies`
--

CREATE TABLE `currencies` (
  `CurrencyID` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `CurrencyName` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `cmc_id` int DEFAULT NULL,
  `Symbol` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `BlockchainID` int NOT NULL,
  `DecimalPlaces` int NOT NULL,
  `IsToken` tinyint(1) DEFAULT '0',
  `SmartContractAddress` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `CreatedAt` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `Icon` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `currencies`
--

INSERT INTO `currencies` (`CurrencyID`, `CurrencyName`, `cmc_id`, `Symbol`, `BlockchainID`, `DecimalPlaces`, `IsToken`, `SmartContractAddress`, `CreatedAt`, `UpdatedAt`, `Icon`) VALUES
('1', 'Bitcoin', 1, 'BTC', 4, 18, 1, '', '2025-02-21 11:29:10', '2025-04-03 18:37:06', 'https://coinceeper.com/CC/cryptoicons/BTC.png'),
('12000', 'Netcoincapital', NULL, 'NCC', 1, 18, 1, '0x3386F545a78eAa832946b59EA10FfDA34275A479', '2025-02-21 11:29:10', '2025-03-30 16:56:56', 'https://coinceeper.com/CC/cryptoicons/NCC.png'),
('16', 'Ethereum', 1027, 'ETH', 1, 18, 0, NULL, '2025-02-21 11:28:19', '2025-04-03 18:19:37', 'https://coinceeper.com/CC/cryptoicons/ETH.png'),
('18', 'Tron', 1958, 'TRX', 2, 18, 0, '0x50327c6c5a14dcade707abad2e27eb517df87ab5', '2025-02-21 11:28:19', '2025-04-04 18:28:32', 'https://coinceeper.com/CC/cryptoicons/TRX.png'),
('2410', 'HarryPotterTrumpSonic100Inu', NULL, 'BTC', 1, 18, 1, '0x7099aB9E42Fa7327a6b15E0a0c120c3e50d11BeC', '2025-04-03 02:25:02', '2025-04-03 02:25:02', 'https://coinceeper.com/CC/cryptoicons/BTC.png'),
('27', 'Shiba Inu', 5994, 'SHIB', 1, 18, 1, '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce', '2025-04-03 02:20:42', '2025-04-03 18:20:28', 'https://coinceeper.com/CC/cryptoicons/SHIB.png'),
('3', 'BNB', 1839, 'BNB', 3, 18, 0, '0xb8c77482e45f1f44de1745f52c74426c631bdd52', '2025-04-03 02:20:42', '2025-04-07 06:47:42', 'https://coinceeper.com/CC/cryptoicons/BNB.png'),
('3012', 'Strategic Hub for Innovation in Blockchain', NULL, 'SHIB', 1, 18, 1, '0xF4b7B9ab55A2eeb3bD6123B8f45B0abfFd5089c7', '2025-04-03 02:25:07', '2025-04-03 02:25:07', 'https://coinceeper.com/CC/cryptoicons/SHIB.png'),
('3694', 'The Infinite Garden', NULL, 'ETH', 1, 18, 1, '0x5e21d1ee5cf0077b314c381720273ae82378d613', '2025-04-03 02:25:51', '2025-04-03 02:25:51', 'https://coinceeper.com/CC/cryptoicons/ETH.png'),
('3722', 'Boost Trump Campaign', NULL, 'BTC', 1, 18, 1, '0x300e0d87f8c95d90cfe4b809baa3a6c90e83b850', '2025-04-03 02:25:52', '2025-04-03 02:25:52', 'https://coinceeper.com/CC/cryptoicons/BTC.png'),
('3784', 'THE TICKER IS', NULL, 'ETH', 1, 18, 1, '0xC94729d93cB660BB346ce0084393015F99810919', '2025-04-03 02:25:52', '2025-04-03 02:25:52', 'https://coinceeper.com/CC/cryptoicons/ETH.png'),
('8517', 'Netcoincapital', NULL, 'NCC', 2, 18, 1, 'T9yYp7JUxypLk7GFhsLRj5jN6ZrNDcH2Cf', '2025-02-21 11:29:10', '2025-02-21 11:29:10', 'https://coinceeper.com/CC/cryptoicons/NCC.png'),
('8518', 'MATIC', 28321, 'MATIC', 5, 18, 0, '0x455e53cbb86018ac2b8092fdcd39d8444affc3f6', '2025-02-21 11:29:10', '2025-04-20 17:12:20', 'https://coinceeper.com/CC/cryptoicons/POL.png'),
('8519', 'Netcoincapital', NULL, 'NCC', 2, 18, 1, 'TCDgp5bwtixaShPifUm7HpZ71C1pe6zif1', '2025-02-21 11:29:10', '2025-02-21 11:29:10', 'https://coinceeper.com/CC/cryptoicons/NCCold.png');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `currencies`
--
ALTER TABLE `currencies`
  ADD PRIMARY KEY (`CurrencyID`),
  ADD KEY `BlockchainID` (`BlockchainID`);

--
-- Constraints for dumped tables
--

--
-- Constraints for table `currencies`
--
ALTER TABLE `currencies`
  ADD CONSTRAINT `currencies_ibfk_1` FOREIGN KEY (`BlockchainID`) REFERENCES `blockchains` (`BlockchainID`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
