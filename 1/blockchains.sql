-- phpMyAdmin SQL Dump
-- version 5.2.2-1.el9
-- https://www.phpmyadmin.net/
--
-- Host: localhost
-- Generation Time: May 10, 2025 at 10:10 AM
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
-- Table structure for table `blockchains`
--

CREATE TABLE `blockchains` (
  `BlockchainID` int NOT NULL,
  `BlockchainName` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `Symbol` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `ChainCode` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `CreatedAt` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `blockchains`
--

INSERT INTO `blockchains` (`BlockchainID`, `BlockchainName`, `Symbol`, `ChainCode`, `CreatedAt`, `UpdatedAt`) VALUES
(1, 'Ethereum', 'ETH', 'ETH', '2024-10-04 22:51:00', '2024-10-04 22:51:00'),
(2, 'Tron', 'TRX', 'TRX', '2024-10-04 22:51:00', '2024-12-05 21:02:12'),
(3, 'Binance Smart Chain', 'BNB', 'BNB', '2024-12-05 21:03:39', '2025-04-30 16:57:04'),
(4, 'Bitcoin', 'BTC', 'BTC', '2025-01-13 15:59:15', '2025-01-13 15:59:15'),
(5, 'Polygon', 'MATIC', 'MATIC', '2025-01-13 15:59:15', '2025-01-13 15:59:15'),
(6, 'Arbitrum', 'ARB', 'ARB', '2025-01-28 05:06:10', '2025-01-28 05:06:10'),
(11, 'XRP', 'XRP', 'XRP', '2025-01-29 00:42:32', '2025-01-29 00:42:32'),
(12, 'Solana', 'SOL', 'SOL', '2025-01-30 11:20:35', '2025-01-30 11:20:35'),
(13, 'Avalanche', 'AVAX', 'AVAX', '2025-01-30 11:20:35', '2025-01-30 11:20:35'),
(14, 'Polkadot', 'DOT', 'DOT', '2025-01-30 11:20:35', '2025-01-30 11:20:35');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `blockchains`
--
ALTER TABLE `blockchains`
  ADD PRIMARY KEY (`BlockchainID`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `blockchains`
--
ALTER TABLE `blockchains`
  MODIFY `BlockchainID` int NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=15;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
