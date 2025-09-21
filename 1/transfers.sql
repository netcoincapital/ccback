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
-- Table structure for table `transfers`
--

CREATE TABLE `transfers` (
  `TransferID` bigint NOT NULL,
  `BlockchainID` int NOT NULL,
  `AddressID` int NOT NULL,
  `WalletID` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `TxHash` varchar(100) NOT NULL,
  `BlockNumber` bigint DEFAULT NULL,
  `Timestamp` datetime DEFAULT NULL,
  `FromAddress` varchar(100) NOT NULL,
  `ToAddress` varchar(100) NOT NULL,
  `Amount` decimal(36,18) NOT NULL,
  `price` decimal(10,2) DEFAULT NULL,
  `TokenSymbol` varchar(50) CHARACTER SET utf8mb3 COLLATE utf8mb3_general_ci DEFAULT NULL,
  `TokenContract` varchar(100) DEFAULT NULL,
  `AssetType` enum('native','token') NOT NULL DEFAULT 'native',
  `Fee` decimal(36,18) DEFAULT NULL,
  `Direction` enum('inbound','outbound') NOT NULL,
  `Status` enum('pending','confirmed','failed') DEFAULT 'pending',
  `IsSuccessful` tinyint(1) DEFAULT '1',
  `ExplorerUrl` varchar(255) DEFAULT NULL,
  `CreatedAt` datetime DEFAULT CURRENT_TIMESTAMP,
  `UpdatedAt` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;

--
-- Dumping data for table `transfers`
--

INSERT INTO `transfers` (`TransferID`, `BlockchainID`, `AddressID`, `WalletID`, `TxHash`, `BlockNumber`, `Timestamp`, `FromAddress`, `ToAddress`, `Amount`, `price`, `TokenSymbol`, `TokenContract`, `AssetType`, `Fee`, `Direction`, `Status`, `IsSuccessful`, `ExplorerUrl`, `CreatedAt`, `UpdatedAt`) VALUES
(700, 1, 18233, 'f097f87f-f327-46a0-92df-30f309c061f8', '0xc10857ed99cbee3063fd457029327767c65967b09a86c2a3b894c367d9f73da6', 23281772, '2025-09-03 09:45:17', '0x8d697d386c175dc7ac25df67f82b3bfbc8ec5be9', '0x4a56ceb9c75fa018c1e2f16474bb1fbd639a6956', 0.001000000000000000, 1.63, 'ETH', NULL, 'native', 0.000026040485667000, 'inbound', 'confirmed', 1, 'https://etherscan.io/tx/0xc10857ed99cbee3063fd457029327767c65967b09a86c2a3b894c367d9f73da6', '2025-09-03 09:45:20', '2025-09-03 09:45:20'),
(701, 1, 18233, 'f097f87f-f327-46a0-92df-30f309c061f8', '0xde076c44a082d0f10f3268c9713d6e0285cbb658493f7e8525742cc1ab80755c', 23303373, '2025-09-06 10:10:22', '0x4a56ceb9c75fa018c1e2f16474bb1fbd639a6956', '0x8d697d386c175dc7ac25df67f82b3bfbc8ec5be9', 0.001991427039136000, 3.25, 'ETH', NULL, 'native', 0.000003155799570000, 'outbound', 'confirmed', 1, 'https://etherscan.io/tx/0xde076c44a082d0f10f3268c9713d6e0285cbb658493f7e8525742cc1ab80755c', '2025-09-06 10:10:26', '2025-09-06 10:10:26'),
(702, 1, 18233, 'f097f87f-f327-46a0-92df-30f309c061f8', '0x92330fd68f03fd168a7ce9cbb3a2988d42fab4c817166b8bcfb9b8ea74578549', 23303391, '2025-09-06 10:13:53', '0x8d697d386c175dc7ac25df67f82b3bfbc8ec5be9', '0x4a56ceb9c75fa018c1e2f16474bb1fbd639a6956', 0.001966103059546000, 3.21, 'ETH', NULL, 'native', 0.000025323979590000, 'inbound', 'confirmed', 1, 'https://etherscan.io/tx/0x92330fd68f03fd168a7ce9cbb3a2988d42fab4c817166b8bcfb9b8ea74578549', '2025-09-06 10:13:57', '2025-09-06 10:13:57');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `transfers`
--
ALTER TABLE `transfers`
  ADD PRIMARY KEY (`TransferID`),
  ADD UNIQUE KEY `unique_transfer` (`TxHash`,`AddressID`,`WalletID`,`Direction`),
  ADD KEY `BlockchainID` (`BlockchainID`),
  ADD KEY `AddressID` (`AddressID`),
  ADD KEY `WalletID` (`WalletID`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `transfers`
--
ALTER TABLE `transfers`
  MODIFY `TransferID` bigint NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=703;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `transfers`
--
ALTER TABLE `transfers`
  ADD CONSTRAINT `transfers_ibfk_1` FOREIGN KEY (`BlockchainID`) REFERENCES `blockchains` (`BlockchainID`),
  ADD CONSTRAINT `transfers_ibfk_2` FOREIGN KEY (`AddressID`) REFERENCES `address` (`AddressID`),
  ADD CONSTRAINT `transfers_ibfk_3` FOREIGN KEY (`WalletID`) REFERENCES `wallets` (`WalletID`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
