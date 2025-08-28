-- Migration to fix historical data constraints
-- Run this after the code changes to update the database schema

-- Remove the problematic unique constraint that was causing conflicts
-- Note: MySQL doesn't support IF EXISTS for DROP INDEX, so we use a procedure
DELIMITER $$

DROP PROCEDURE IF EXISTS DropIndexIfExists$$
CREATE PROCEDURE DropIndexIfExists()
BEGIN
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION BEGIN END;
    ALTER TABLE prices DROP INDEX unique_crypto_currency;
END$$

CALL DropIndexIfExists()$$
DROP PROCEDURE DropIndexIfExists$$

DELIMITER ;

-- Add better indexes for performance
-- Note: MySQL doesn't support IF NOT EXISTS for CREATE INDEX in older versions
DELIMITER $$

DROP PROCEDURE IF EXISTS CreateIndexIfNotExists$$
CREATE PROCEDURE CreateIndexIfNotExists()
BEGIN
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION BEGIN END;
    
    -- Historical data lookup index
    CREATE INDEX idx_prices_historical_lookup 
    ON prices (crypto_id, currency, is_historical, timestamp);
    
    -- Current price lookup index  
    CREATE INDEX idx_prices_current_lookup
    ON prices (crypto_id, currency, is_historical);
    
END$$

CALL CreateIndexIfNotExists()$$
DROP PROCEDURE CreateIndexIfNotExists$$

DELIMITER ;

-- Update any existing records to ensure string format for crypto_id
UPDATE prices SET crypto_id = CAST(crypto_id AS CHAR) WHERE crypto_id REGEXP '^[0-9]+$';

-- Ensure all historical records have proper timestamps
UPDATE prices SET timestamp = last_updated WHERE is_historical = 1 AND timestamp IS NULL;

-- Add comment for future reference
ALTER TABLE prices COMMENT = 'Updated for historical data support - constraint unique_crypto_currency removed';
