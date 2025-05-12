-- phpMyAdmin SQL Dump
-- version 5.2.2-1.el9
-- https://www.phpmyadmin.net/
--
-- Host: localhost
-- Generation Time: May 12, 2025 at 01:04 AM
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
-- Table structure for table `address`
--

CREATE TABLE `address` (
  `AddressID` int NOT NULL,
  `WalletID` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `BlockchainID` int NOT NULL,
  `PublicAddress` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `PrivateKey` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `PhraseKey` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `CreatedAt` timestamp NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `address`
--

INSERT INTO `address` (`AddressID`, `WalletID`, `BlockchainID`, `PublicAddress`, `PrivateKey`, `PhraseKey`, `CreatedAt`) VALUES
(10231, '279ddfeb-523a-4216-8893-9f22eff09e1b', 4, 'bc1qsjgpcszqwjcujrleh3r4ucyg2zkl6k0a9s5dkm', 'oUNsyCEhH2TCkcgnPDS36uTO26DRcPjxIBQlYBRPxH+Sm/rDA2ah2tVjKLhhontv0bsOcNSDb+Nqo6jIiVbPH5ZpODSXheJSXpOVBlGnlZlzFo6H', 'bwY/DktcMu58+lqDvFTSLHDi3T0q5iIEYCNAGZwt6sURSkyMo7sA3H8++eo5d438m6t7u/8tJwcDvDZhro8M0XpzSqqsWAC+1GyzA+Bth/ITGLOxj8b+ao4W/LhdOWAVyzDMnknynoR3tNOSeEDv3Gzb/6Z+z13DhoGFk4g9TyMDV1TvQtpMiQ==', '2025-05-02 11:22:49'),
(10232, '279ddfeb-523a-4216-8893-9f22eff09e1b', 1, '0xb944f84569b9F32fF12443Fbdc6FF38A605C4e2A', 'N20GNtvoxSLvsQP+V6NUORHU60ZgzxuEZyhSGbFpyATStz65kLFSinyoGcgns/D4gd7PZGS5/atC3JhuBZUkwEfr+5XQClkqZIBR9xcQiwgugXUCY4wKESa+DDjLFlmu', 'zO9qbRG6JwT+sty3zLg03LMliRV2A3324MDzEBMpoXLDZEJgdEbZ2QJjEelVU5klgodpti0CTAa7i/ssuhIoxwvG+5aNFHT6VMuS0oa38rf9bKgISBm0KLnNiisRnpD7qPbVfT1+cAmCFMB7UTHT2ESYAPPrU48KJTHMbnUMtcQZlArBoUAdKA==', '2025-05-02 11:22:49'),
(10233, '279ddfeb-523a-4216-8893-9f22eff09e1b', 2, 'TVBLMXUejZXsA1PWS49gjgeqY39H3MDkpx', 'MUVjZ9R7HhdVvWJRF1UZpLd/xh84Ry9YaEjEoXzQw3sdoFk3Erg4haWk7MM8SYHDGFylTuTuTQ+Nt30u2TxZpAw/iLGAMiBiuxZ0wWasmnlvgqplUua1bLd3Lzjzt/hE', 'SpyZ8f10Ipw2vOM1UtnjDdj/O/JNw3gErtbhAihRaznicpw8b6YGYs9ktQpztzdKngvdKpXfs/JzCJq38JcckNVlHdgWTFNnlRcyrcKNh84lvlGKtqCilNJs1vaRc074C/fhES2a5m5nm7BbO0O5Anz/kRYBOw73NoZSl7IdxsCk9PY56A7ZHQ==', '2025-05-02 11:22:49'),
(10234, '279ddfeb-523a-4216-8893-9f22eff09e1b', 3, '0xb944f84569b9F32fF12443Fbdc6FF38A605C4e2A', 'CCTHfyC4J331zBZj8igVZLx3+DHkq/G6i51SWzBwAb42BjzawjyBvKS1OpY0i3Fw967NFtFyZnAJVYDVcFoBggUQzK7vxX5akXzuusSfOs3qagd7pbXoVQAKhYMRaKuF', 'BqU7g5l7RVWRkrJ5QL2GpzCHBNKg7DWSWr2XMMDwa6A+2NgvMDotbov5pt61Cz1+SRKtqhOonpiQm6ZBcP+GFfdHW1gp5ZFyXAu3sFPyRfqmrBnFPhh8RQIVn+ZclcYfXj6XeypVG1uhfO9u9YKDuoyILIn7Z0wmEi1cGhaKUPXrcZ1D4A1/Qg==', '2025-05-02 11:22:49'),
(10235, '279ddfeb-523a-4216-8893-9f22eff09e1b', 5, '0xb944f84569b9F32fF12443Fbdc6FF38A605C4e2A', 'uZCFTqwF4Ow0XQVifIDwvye84Ze40VzO70hTB2yOn7xk/EJ2nX1hItgQVk1G17nOXAR4vYR3+3xGXON2b6lYJXjzH5BbCvZzCKP2bkAUoBKzkJQ48RhyaKvtaTaQTRrd', 'vxXcC9XnkW1nzcgyIRF/CNqq/ujJUFaV5y2QIZuRqh4OTylPsRBT4dYwKSDyeM8kM0S5s4tu9pVMmRRwH7FQ/0J8XxmQytYVlIKP9Nj7pMWgtULy8oU4qBTA7hZknh+wQyWTFlG8WtP7jmXluT5F6BvFkILuRyIZfV9scsCFe9ouaF8p7DleCQ==', '2025-05-02 11:22:49'),
(10236, '279ddfeb-523a-4216-8893-9f22eff09e1b', 13, '0xb944f84569b9F32fF12443Fbdc6FF38A605C4e2A', '8Osm76MMcQqV6iPZ23EegjqYJ1oYo87sNXpLipuAVHeqF81enEIK5ZAmx0qvhHCTOvjnYDCJa5eKtoFEkSrnxUk6+wk82ZgGJ0W/MCdvOrQxjeV3iN6JphhcM6vQAyZC', 'R2xvt1KaUG1N+XexK/n1kOgPC/2oCeu4za4rvZ1kMWMKMSlL9RbeAwA3p6oa/lB9fcohGZ5i2+cgjDHMVi9UhVmTCmeaBCZKlFcs39CS0w3p/2oPiriCtTNgOxmR6+bWqLuGmeb6aZaBj02djKeA4WzxvPiPzdSh76LNo4iVBFJlDPJeVONGzA==', '2025-05-02 11:22:49'),
(10237, '279ddfeb-523a-4216-8893-9f22eff09e1b', 6, '0xb944f84569b9F32fF12443Fbdc6FF38A605C4e2A', 'aPpjcbCVFEPj25YbNdjzuDq1Gbo5vnBgb4z5uq/v62qS7z2r3pPT/qsxGuEN81UvhTW+FHj+NdSNDndefhWGa2Vfl0ApS6oErCpmZXYmp5+Z6ssIdoOWbX56oELQBSzK', 'aIqZ8oVS5iwUrmAyigS0dPuGroMCC/qne2rTVdjgjiZw9HEAC2RFj3tpSEGjolPtJY4qpDcJZXHqGd4pl/0t3lcm7pwqYMquclaUKoN3SH2Jm6UnoywYRibLpQ9idAH+ErICjowp/eg0kTM+HmpwUlIlTli/5EpREeBLwYwfaARqFjna6XZWeQ==', '2025-05-02 11:22:49'),
(10238, '279ddfeb-523a-4216-8893-9f22eff09e1b', 14, '13VDwe5MzrHiCTzwgbMnoiQgk9X93Pwt36eKUgC3kssRfkqv', '1J3S9za0+NljFyZOJQblaUWrtNOXotuLpEUX2iqiMS6GMOOPB74dBEl8ohEMreV3lqlOpeWCLz58qTpURgBEqIZ/ldRSlrNb9+PiuAaQQ/4DNEAlyonHaA4J578zELJc', 'VhhZVzhfaTjQB6a2MgXrbLtRLpcbztoHgRuP0GD/nMkOvY+ZLgKFwwh0W0OgZYddaWXF1gq5jJtiG7Cwv4R33SPHLmtaCq7J29F/sxW9MZvqttH+X0rewK/ghf+24ly2rdmdbC1zCQe6HKld4eEIbEfCi1XNp0Vj/T632yVyUPLLpclvjEHpzw==', '2025-05-02 11:22:49'),
(10239, '279ddfeb-523a-4216-8893-9f22eff09e1b', 11, 'rGSKzVMCKpZDZNvRm3pwHKoZnYEhKsAk1u', 'DajlGnm0xHSMoRI8GltsDmunx9vU/EX5WKI/9XwT+NvAzilvQ3PNF5UcpmFdx11tGp17yFLMdI0jRLPudA2TqBoibxdLDMBQEJ8kaMmCrI0D+wsQ+5XE5yxU6U94wGFb', 'P43HkwAFVdLQ7lC1phrflif7aKNGK3kFXN4VLifl0p9GNETq+8F+oprDLVRmGKiQpBvbYifkNiramGCTDwtwcoRGVcQ8CFwZ4OR7dxkz3PtMUMgYVBaZOs22Vn0+WaUOZf3MgaQpuz7hH1Bqn/4xHZrO2ul17Sz7TkT0HNJUvOb/1tWNdFTMJw==', '2025-05-02 11:22:49');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `address`
--
ALTER TABLE `address`
  ADD PRIMARY KEY (`AddressID`),
  ADD KEY `WalletID` (`WalletID`),
  ADD KEY `BlockchainID` (`BlockchainID`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `address`
--
ALTER TABLE `address`
  MODIFY `AddressID` int NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=10261;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `address`
--
ALTER TABLE `address`
  ADD CONSTRAINT `address_ibfk_1` FOREIGN KEY (`WalletID`) REFERENCES `wallets` (`WalletID`),
  ADD CONSTRAINT `address_ibfk_2` FOREIGN KEY (`BlockchainID`) REFERENCES `blockchains` (`BlockchainID`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
