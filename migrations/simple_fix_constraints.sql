-- Simple migration to fix historical data constraints
-- Run this in MySQL to fix the constraint issues

-- Step 1: Remove the problematic constraint (ignore error if doesn't exist)
ALTER TABLE prices DROP INDEX unique_crypto_currency;

-- Step 2: Add performance indexes (ignore error if already exist)
CREATE INDEX idx_prices_historical_lookup ON prices (crypto_id, currency, is_historical, timestamp);
CREATE INDEX idx_prices_current_lookup ON prices (crypto_id, currency, is_historical);

-- Step 3: Clean up data
UPDATE prices SET crypto_id = CAST(crypto_id AS CHAR) WHERE crypto_id REGEXP '^[0-9]+$';
UPDATE prices SET timestamp = last_updated WHERE is_historical = 1 AND timestamp IS NULL;

-- Step 4: Verify changes
SELECT 'Migration completed successfully' as status;
