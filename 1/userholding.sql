-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: localhost
-- Generation Time: Sep 06, 2025 at 10:45 AM
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
-- Table structure for table `userholding`
--

CREATE TABLE `userholding` (
  `HoldingID` int NOT NULL,
  `UserID` char(36) NOT NULL,
  `CurrencyID` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `Balance` decimal(38,18) NOT NULL DEFAULT '0.000000000000000000',
  `Symbol` varchar(20) NOT NULL,
  `Blockchain` varchar(50) NOT NULL,
  `IsToken` tinyint(1) NOT NULL DEFAULT '0',
  `SmartContractAddress` varchar(255) DEFAULT NULL,
  `LastUpdated` timestamp NULL DEFAULT NULL,
  `RawData` json DEFAULT NULL,
  `CreatedAt` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

--
-- Dumping data for table `userholding`
--

INSERT INTO `userholding` (`HoldingID`, `UserID`, `CurrencyID`, `Balance`, `Symbol`, `Blockchain`, `IsToken`, `SmartContractAddress`, `LastUpdated`, `RawData`, `CreatedAt`, `UpdatedAt`) VALUES
(1620, '63ff3616-abb3-4d03-b8d6-51a3c5a6dc08', '16', 0.003932206119092000, 'ETH', 'ETH', 0, NULL, NULL, NULL, '2025-09-03 09:45:19', '2025-09-06 10:14:14');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `userholding`
--
ALTER TABLE `userholding`
  ADD PRIMARY KEY (`HoldingID`),
  ADD UNIQUE KEY `uix_user_token_contract` (`UserID`,`Symbol`,`Blockchain`,`SmartContractAddress`),
  ADD KEY `fk_currency` (`CurrencyID`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `userholding`
--
ALTER TABLE `userholding`
  MODIFY `HoldingID` int NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=1621;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `userholding`
--
ALTER TABLE `userholding`
  ADD CONSTRAINT `fk_currency` FOREIGN KEY (`CurrencyID`) REFERENCES `currencies` (`CurrencyID`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
