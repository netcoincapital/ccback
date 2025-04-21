#!/usr/bin/env python3
# update_transaction_prices.py - Script to update existing transaction Price values

from sqlalchemy.orm import Session
from database import engine, Transfers, Price, Currencies
from decimal import Decimal
import logging
import sys

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('update_transaction_prices')

def get_token_price(session, token_symbol):
    """Get the current price for a token from prices table"""
    logger.info(f"Looking up price for token: {token_symbol}")
    
    price_record = session.query(Price).join(
        Currencies, 
        Price.crypto_id == Currencies.CurrencyID
    ).filter(
        Currencies.Symbol == token_symbol,
        Price.currency == 'USD'  # Default to USD
    ).first()
    
    if price_record:
        logger.info(f"Found price for {token_symbol}: {price_record.price}")
        return price_record.price
    
    logger.warning(f"No price found for {token_symbol}")
    return Decimal('0')

def update_all_transfers():
    """Update all transfer records to have the correct Price value"""
    logger.info("Starting update of all transfer records")
    
    with Session(engine) as session:
        try:
            # Get count of transfers
            total_transfers = session.query(Transfers).count()
            logger.info(f"Found {total_transfers} transfer records to update")
            
            # Process in batches to avoid memory issues
            batch_size = 100
            updated_count = 0
            error_count = 0
            
            for offset in range(0, total_transfers, batch_size):
                batch = session.query(Transfers).limit(batch_size).offset(offset).all()
                
                if not batch:
                    logger.info(f"No more records found after offset {offset}")
                    break
                
                logger.info(f"Processing batch of {len(batch)} records from offset {offset}")
                
                for transfer in batch:
                    try:
                        # Skip records that already have a Price value
                        if transfer.Price is not None and transfer.Price > 0:
                            continue
                            
                        # Get the price for this token
                        token_price = get_token_price(session, transfer.TokenSymbol)
                        
                        # Calculate the transaction value (amount * price)
                        old_value = transfer.Price
                        transaction_value = transfer.Amount * token_price
                        
                        # Update the Price field
                        transfer.Price = transaction_value
                        logger.info(f"Updated transfer ID {transfer.TransferID}: {transfer.Amount} {transfer.TokenSymbol} × {token_price} = {transaction_value}")
                        
                        updated_count += 1
                        
                    except Exception as transfer_error:
                        logger.error(f"Error updating transfer ID {transfer.TransferID}: {str(transfer_error)}", exc_info=True)
                        error_count += 1
                
                # Commit after each batch
                session.commit()
                logger.info(f"Committed batch of {len(batch)} records")
            
            logger.info(f"Update completed. Updated {updated_count} records. Errors: {error_count}")
            return updated_count
            
        except Exception as e:
            logger.error(f"Error updating transfer records: {str(e)}", exc_info=True)
            session.rollback()
            return 0

def update_specific_transfer(transfer_id):
    """Update a specific transfer record"""
    logger.info(f"Updating transfer ID: {transfer_id}")
    
    with Session(engine) as session:
        try:
            transfer = session.query(Transfers).filter(Transfers.TransferID == transfer_id).first()
            
            if not transfer:
                logger.error(f"Transfer ID {transfer_id} not found")
                return False
                
            # Get the price for this token
            token_price = get_token_price(session, transfer.TokenSymbol)
            
            # Calculate the transaction value (amount * price)
            old_value = transfer.Price
            transaction_value = transfer.Amount * token_price
            
            # Update the Price field
            transfer.Price = transaction_value
            
            # Commit the change
            session.commit()
            
            logger.info(f"Updated transfer ID {transfer_id}: {transfer.Amount} {transfer.TokenSymbol} × {token_price} = {transaction_value} (was: {old_value})")
            return True
            
        except Exception as e:
            logger.error(f"Error updating transfer ID {transfer_id}: {str(e)}", exc_info=True)
            session.rollback()
            return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python update_transaction_prices.py all - Update all transfer records")
        print("  python update_transaction_prices.py transfer_id TRANSFER_ID - Update a specific transfer record")
        sys.exit(1)
        
    command = sys.argv[1]
    
    if command == "all":
        update_all_transfers()
    elif command == "transfer_id" and len(sys.argv) == 3:
        try:
            transfer_id = int(sys.argv[2])
            update_specific_transfer(transfer_id)
        except ValueError:
            logger.error(f"Invalid transfer ID: {sys.argv[2]}")
            sys.exit(1)
    else:
        print("Invalid command or missing arguments")
        sys.exit(1) 