#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db_connection_string

def migrate_symbols(old_engine, new_engine):
    logger.info("Migrating currencies to symbols table...")
    
    with old_engine.connect() as old_conn, new_engine.connect() as new_conn:
        result = old_conn.execute(text("""
            SELECT CurrencyID, Symbol, Name, CMC_ID, CoinGecko_ID, IsActive
            FROM currencies
            ORDER BY CurrencyID
        """))
        
        currencies = result.fetchall()
        logger.info(f"Found {len(currencies)} currencies to migrate")
        
        for curr in currencies:
            new_conn.execute(text("""
                INSERT INTO symbols (id, symbol, name, cmc_id, coingecko_id, is_active)
                VALUES (:id, :symbol, :name, :cmc_id, :coingecko_id, :is_active)
                ON DUPLICATE KEY UPDATE
                    symbol = VALUES(symbol),
                    name = VALUES(name),
                    cmc_id = VALUES(cmc_id),
                    coingecko_id = VALUES(coingecko_id),
                    is_active = VALUES(is_active)
            """), {
                'id': curr[0],
                'symbol': curr[1],
                'name': curr[2],
                'cmc_id': curr[3],
                'coingecko_id': curr[4],
                'is_active': curr[5] or 1
            })
        
        new_conn.commit()
        logger.info(f"✓ Migrated {len(currencies)} symbols")

def migrate_current_prices(old_engine, new_engine):
    logger.info("Migrating current prices (USD only)...")
    
    with old_engine.connect() as old_conn, new_engine.connect() as new_conn:
        result = old_conn.execute(text("""
            SELECT 
                p.crypto_id,
                p.price,
                p.volume_24h,
                p.market_cap,
                p.change_1h,
                p.change_24h,
                p.change_7d,
                p.last_updated
            FROM prices p
            INNER JOIN (
                SELECT crypto_id, MAX(timestamp) as max_ts
                FROM prices
                WHERE currency = 'USD' AND is_historical = 0
                GROUP BY crypto_id
            ) latest ON p.crypto_id = latest.crypto_id AND p.timestamp = latest.max_ts
            WHERE p.currency = 'USD'
        """))
        
        prices = result.fetchall()
        logger.info(f"Found {len(prices)} current prices to migrate")
        
        for price in prices:
            new_conn.execute(text("""
                INSERT INTO current_prices 
                (symbol_id, price, volume_24h, market_cap, change_1h, change_24h, change_7d, last_updated)
                VALUES (:symbol_id, :price, :volume_24h, :market_cap, :change_1h, :change_24h, :change_7d, :last_updated)
                ON DUPLICATE KEY UPDATE
                    price = VALUES(price),
                    volume_24h = VALUES(volume_24h),
                    market_cap = VALUES(market_cap),
                    change_1h = VALUES(change_1h),
                    change_24h = VALUES(change_24h),
                    change_7d = VALUES(change_7d),
                    last_updated = VALUES(last_updated)
            """), {
                'symbol_id': price[0],
                'price': price[1],
                'volume_24h': price[2],
                'market_cap': price[3],
                'change_1h': price[4],
                'change_24h': price[5],
                'change_7d': price[6],
                'last_updated': price[7]
            })
        
        new_conn.commit()
        logger.info(f"✓ Migrated {len(prices)} current prices")

def migrate_recent_ticks(old_engine, new_engine, days=7):
    logger.info(f"Migrating recent ticks (last {days} days, USD only)...")
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    with old_engine.connect() as old_conn, new_engine.connect() as new_conn:
        result = old_conn.execute(text("""
            SELECT 
                crypto_id,
                price,
                volume_24h,
                market_cap,
                timestamp
            FROM prices
            WHERE currency = 'USD' 
              AND timestamp >= :cutoff_date
            ORDER BY timestamp
        """), {'cutoff_date': cutoff_date})
        
        batch = []
        batch_size = 1000
        total = 0
        
        for row in result:
            batch.append({
                'symbol_id': row[0],
                'price': row[1],
                'volume_24h': row[2],
                'market_cap': row[3],
                'timestamp': row[4]
            })
            
            if len(batch) >= batch_size:
                new_conn.execute(text("""
                    INSERT IGNORE INTO ticks_recent 
                    (symbol_id, price, volume_24h, market_cap, timestamp)
                    VALUES (:symbol_id, :price, :volume_24h, :market_cap, :timestamp)
                """), batch)
                new_conn.commit()
                total += len(batch)
                logger.info(f"  Migrated {total} ticks...")
                batch = []
        
        if batch:
            new_conn.execute(text("""
                INSERT IGNORE INTO ticks_recent 
                (symbol_id, price, volume_24h, market_cap, timestamp)
                VALUES (:symbol_id, :price, :volume_24h, :market_cap, :timestamp)
            """), batch)
            new_conn.commit()
            total += len(batch)
        
        logger.info(f"✓ Migrated {total} recent ticks")

def create_candles_from_ticks(new_engine, interval='1m', days=30):
    logger.info(f"Creating {interval} candles from ticks (last {days} days)...")
    
    if interval == '1m':
        table = 'candles_1m'
        time_format = '%Y-%m-%d %H:%i:00'
    elif interval == '1h':
        table = 'candles_1h'
        time_format = '%Y-%m-%d %H:00:00'
    elif interval == '1d':
        table = 'candles_1d'
        time_format = '%Y-%m-%d'
    else:
        raise ValueError(f"Unknown interval: {interval}")
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    with new_engine.connect() as conn:
        result = conn.execute(text(f"""
            INSERT INTO {table} (symbol_id, open_price, high_price, low_price, close_price, volume, timestamp)
            SELECT 
                symbol_id,
                SUBSTRING_INDEX(GROUP_CONCAT(price ORDER BY timestamp ASC), ',', 1) as open_price,
                MAX(price) as high_price,
                MIN(price) as low_price,
                SUBSTRING_INDEX(GROUP_CONCAT(price ORDER BY timestamp DESC), ',', 1) as close_price,
                SUM(volume_24h) / COUNT(*) as volume,
                STR_TO_DATE(DATE_FORMAT(timestamp, '{time_format}'), '{time_format}') as candle_time
            FROM ticks_recent
            WHERE timestamp >= :cutoff_date
            GROUP BY symbol_id, candle_time
            ON DUPLICATE KEY UPDATE
                open_price = VALUES(open_price),
                high_price = VALUES(high_price),
                low_price = VALUES(low_price),
                close_price = VALUES(close_price),
                volume = VALUES(volume)
        """), {'cutoff_date': cutoff_date})
        
        conn.commit()
        logger.info(f"✓ Created {interval} candles")

def main():
    logger.info("=" * 60)
    logger.info("Starting Migration to New Price Schema")
    logger.info("=" * 60)
    
    db_string = get_db_connection_string()
    old_engine = create_engine(db_string, pool_pre_ping=True)
    new_engine = create_engine(db_string, pool_pre_ping=True)
    
    try:
        logger.info("\n1. Creating new schema...")
        with open('database/new_price_schema.sql', 'r') as f:
            schema_sql = f.read()
        
        with new_engine.connect() as conn:
            for statement in schema_sql.split(';'):
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    try:
                        conn.execute(text(statement))
                    except Exception as e:
                        if 'already exists' not in str(e).lower():
                            logger.warning(f"Statement error: {e}")
            conn.commit()
        logger.info("✓ Schema created")
        
        logger.info("\n2. Migrating symbols...")
        migrate_symbols(old_engine, new_engine)
        
        logger.info("\n3. Migrating current prices...")
        migrate_current_prices(old_engine, new_engine)
        
        logger.info("\n4. Migrating recent ticks (7 days)...")
        migrate_recent_ticks(old_engine, new_engine, days=7)
        
        logger.info("\n5. Creating 1m candles...")
        create_candles_from_ticks(new_engine, '1m', days=7)
        
        logger.info("\n6. Creating 1h candles...")
        create_candles_from_ticks(new_engine, '1h', days=30)
        
        logger.info("\n7. Creating 1d candles...")
        create_candles_from_ticks(new_engine, '1d', days=365)
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ Migration completed successfully!")
        logger.info("=" * 60)
        
        logger.info("\nNext steps:")
        logger.info("1. Test the new API endpoints")
        logger.info("2. Update price collection service to use new schema")
        logger.info("3. After verification, rename 'prices' table to 'prices_old'")
        logger.info("4. Monitor performance for a few days")
        logger.info("5. Drop 'prices_old' table to free up 13GB")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

