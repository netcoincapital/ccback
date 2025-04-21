#!/usr/bin/env python3
# manual_price_update.py - Script to manually add/update prices in the database

from sqlalchemy.orm import Session
from database import engine, Price, Currencies
from decimal import Decimal
import logging
import sys

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('manual_price_update')

def add_price(currency_symbol, price_value):
    """Add or update price for a given currency symbol"""
    logger.info(f"Adding/updating price for {currency_symbol} to ${price_value}")
    
    with Session(engine) as session:
        try:
            # First find the currency by symbol
            currency = session.query(Currencies).filter(
                Currencies.Symbol == currency_symbol
            ).first()
            
            if not currency:
                logger.error(f"Currency with symbol '{currency_symbol}' not found in database")
                return False
                
            logger.info(f"Found currency: {currency.CurrencyID} - {currency.CurrencyName}")
                
            # Check if price already exists
            existing_price = session.query(Price).filter(
                Price.crypto_id == currency.CurrencyID,
                Price.currency == 'USD'
            ).first()
            
            if existing_price:
                # Update existing price
                logger.info(f"Updating existing price record: {existing_price.price} → {price_value}")
                existing_price.price = price_value
            else:
                # Create new price record
                logger.info(f"Creating new price record for {currency_symbol}: ${price_value}")
                new_price = Price(
                    crypto_id=currency.CurrencyID,
                    currency='USD',
                    price=price_value
                )
                session.add(new_price)
                
            # Commit changes
            session.commit()
            logger.info(f"Price for {currency_symbol} successfully saved to database")
            return True
            
        except Exception as e:
            logger.error(f"Error adding/updating price: {str(e)}", exc_info=True)
            session.rollback()
            return False

def list_currencies():
    """List all available currencies in the database"""
    logger.info("Listing all currencies in database:")
    
    with Session(engine) as session:
        try:
            currencies = session.query(Currencies).all()
            
            if not currencies:
                logger.info("No currencies found in database")
                return
                
            logger.info(f"Found {len(currencies)} currencies:")
            for currency in currencies:
                logger.info(f"ID: {currency.CurrencyID}, Symbol: {currency.Symbol}, Name: {currency.CurrencyName}")
                
        except Exception as e:
            logger.error(f"Error listing currencies: {str(e)}", exc_info=True)

def list_prices():
    """List all prices in the database"""
    logger.info("Listing all prices in database:")
    
    with Session(engine) as session:
        try:
            prices = session.query(Price).all()
            
            if not prices:
                logger.info("No prices found in database")
                return
                
            logger.info(f"Found {len(prices)} price records:")
            for price in prices:
                currency = session.query(Currencies).filter(Currencies.CurrencyID == price.crypto_id).first()
                symbol = currency.Symbol if currency else "Unknown"
                logger.info(f"ID: {price.id}, Symbol: {symbol}, Price: ${price.price}, Currency: {price.currency}")
                
        except Exception as e:
            logger.error(f"Error listing prices: {str(e)}", exc_info=True)

def add_default_prices():
    """Add default prices for popular cryptocurrencies"""
    logger.info("Adding default prices for popular cryptocurrencies")
    
    default_prices = {
        "BTC": "45000.00",  # Bitcoin
        "ETH": "3200.00",   # Ethereum
        "BNB": "400.00",    # Binance Coin
        "BSC": "400.00",    # BSC (same as BNB)
        "MATIC": "0.75",    # Polygon
        "TRX": "0.12",      # Tron
        "SOL": "100.00",    # Solana
        "ADA": "0.40",      # Cardano
        "AVAX": "28.00",    # Avalanche
        "USDT": "1.00",     # Tether
        "USDC": "1.00",     # USD Coin
    }
    
    success_count = 0
    for symbol, price in default_prices.items():
        if add_price(symbol, Decimal(price)):
            success_count += 1
            
    logger.info(f"Successfully added/updated {success_count} out of {len(default_prices)} prices")
    
    # List all prices after update
    list_prices()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python manual_price_update.py list_currencies - List all currencies")
        print("  python manual_price_update.py list_prices - List all prices")
        print("  python manual_price_update.py add_defaults - Add default prices")
        print("  python manual_price_update.py add SYMBOL PRICE - Add/update price for a symbol")
        sys.exit(1)
        
    command = sys.argv[1]
    
    if command == "list_currencies":
        list_currencies()
    elif command == "list_prices":
        list_prices()
    elif command == "add_defaults":
        add_default_prices()
    elif command == "add" and len(sys.argv) == 4:
        symbol = sys.argv[2]
        try:
            price = Decimal(sys.argv[3])
            add_price(symbol, price)
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            sys.exit(1)
    else:
        print("Invalid command or missing arguments")
        sys.exit(1) 