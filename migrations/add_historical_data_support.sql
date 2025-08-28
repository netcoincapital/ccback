-- Migration: Add historical data support to prices table
-- Date: 2025-01-18
-- Description: Add columns to support historical price data for charts

-- Add new columns to prices table
ALTER TABLE prices 
ADD COLUMN is_historical BOOLEAN NOT NULL DEFAULT FALSE,
ADD COLUMN timestamp DATETIME NULL;

-- Drop existing unique constraint
ALTER TABLE prices DROP INDEX unique_crypto_currency;

-- Add new unique constraint that includes timestamp
ALTER TABLE prices 
ADD CONSTRAINT unique_crypto_currency_timestamp 
UNIQUE (crypto_id, currency, timestamp);

-- Add back the original constraint for current prices (where timestamp is NULL)
ALTER TABLE prices 
ADD CONSTRAINT unique_crypto_currency 
UNIQUE (crypto_id, currency);

-- Add indexes for better performance
CREATE INDEX timestamp_idx ON prices (timestamp);
CREATE INDEX historical_idx ON prices (is_historical);

-- Update existing records to mark them as non-historical
UPDATE prices SET is_historical = FALSE WHERE is_historical IS NULL;
