#!/usr/bin/env python3
"""
اسکریپت بازسازی موجودی کاربران از پایه

این اسکریپت کلیه موجودی‌های کاربران را براساس تراکنش‌ها از صفر محاسبه می‌کند
به عنوان یک ابزار تعمیراتی برای زمانی که موجودی‌ها ناهماهنگی دارند استفاده می‌شود
"""

import sys
import os
import logging
from decimal import Decimal
from datetime import datetime
import argparse

# اضافه کردن مسیر پروژه به سیستم
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, Users, Wallets, Address, Transfers, UserHolding, Blockchains, Currencies
from sqlalchemy import func, text
from utils.logging_config import setup_logging, get_logger

# تنظیم لاگر
setup_logging()
logger = get_logger(__name__)

def rebuild_user_balance(user_id=None, force=False, dry_run=True):
    """
    بازسازی موجودی کاربران از تراکنش‌ها
    
    Args:
        user_id (str): شناسه کاربر (اگر None باشد، برای همه کاربران انجام می‌شود)
        force (bool): آیا موجودی‌های موجود پاک شوند
        dry_run (bool): اگر True باشد، فقط تغییرات را نمایش می‌دهد بدون اعمال آنها
    """
    logger.info(f"Starting balance rebuild for {'user ' + user_id if user_id else 'all users'}")
    logger.info(f"Mode: {'Dry run (no changes will be made)' if dry_run else 'Live run (changes will be applied)'}")
    
    session = SessionLocal()
    
    try:
        # جستجوی کاربران
        query = session.query(Users)
        if user_id:
            query = query.filter(Users.UserID == user_id)
        
        users = query.all()
        logger.info(f"Found {len(users)} users to process")
        
        for user in users:
            logger.info(f"Processing user {user.UserID}")
            
            # دریافت کیف پول‌های کاربر
            wallets = session.query(Wallets).filter(Wallets.UserID == user.UserID).all()
            wallet_ids = [w.WalletID for w in wallets]
            
            logger.info(f"Found {len(wallets)} wallets for user {user.UserID}")
            
            if not wallets:
                logger.warning(f"No wallets found for user {user.UserID}")
                continue
            
            # دریافت تراکنش‌های منحصر به فرد برای محاسبه توکن‌ها
            unique_tokens = session.query(
                Transfers.TokenSymbol,
                Transfers.BlockchainID
            ).filter(
                Transfers.WalletID.in_(wallet_ids),
                Transfers.IsSuccessful == True
            ).distinct().all()
            
            logger.info(f"Found {len(unique_tokens)} unique tokens for user {user.UserID}")
            
            # در صورت نیاز، پاک کردن موجودی‌های موجود
            if force and not dry_run:
                deleted = session.query(UserHolding).filter(UserHolding.UserID == user.UserID).delete()
                logger.info(f"Deleted {deleted} existing holdings for user {user.UserID}")
            
            # پردازش هر توکن
            for token_info in unique_tokens:
                token_symbol = token_info.TokenSymbol
                blockchain_id = token_info.BlockchainID
                
                if not token_symbol:
                    logger.warning(f"Skipping token with empty symbol for blockchain ID {blockchain_id}")
                    continue
                
                # دریافت اطلاعات بلاکچین
                blockchain = session.query(Blockchains).filter(Blockchains.BlockchainID == blockchain_id).first()
                if not blockchain:
                    logger.warning(f"Blockchain with ID {blockchain_id} not found")
                    continue
                
                blockchain_name = blockchain.BlockchainName
                
                # محاسبه موجودی
                inbound_sum = session.query(func.sum(Transfers.Amount)).filter(
                    Transfers.WalletID.in_(wallet_ids),
                    Transfers.TokenSymbol == token_symbol,
                    Transfers.BlockchainID == blockchain_id,
                    Transfers.Direction == 'inbound',
                    Transfers.IsSuccessful == True
                ).scalar() or Decimal('0')
                
                outbound_sum = session.query(func.sum(Transfers.Amount)).filter(
                    Transfers.WalletID.in_(wallet_ids),
                    Transfers.TokenSymbol == token_symbol,
                    Transfers.BlockchainID == blockchain_id,
                    Transfers.Direction == 'outbound',
                    Transfers.IsSuccessful == True
                ).scalar() or Decimal('0')
                
                # محاسبه موجودی نهایی
                balance = max(inbound_sum - outbound_sum, Decimal('0'))
                
                if balance <= 0:
                    logger.info(f"Skipping zero balance for token {token_symbol} on {blockchain_name}")
                    continue
                
                logger.info(f"Calculated balance for {token_symbol} on {blockchain_name}: {balance}")
                
                # دریافت یا ایجاد رکورد ارز
                currency = session.query(Currencies).filter(
                    Currencies.Symbol == token_symbol,
                    Currencies.BlockchainID == blockchain_id
                ).first()
                
                if not currency:
                    logger.warning(f"Currency {token_symbol} on {blockchain_name} not found, creating placeholder")
                    
                    # این بخش در حالت dry run اجرا نمی‌شود
                    if not dry_run:
                        # دریافت نمونه تراکنش برای اطلاعات بیشتر
                        sample_transfer = session.query(Transfers).filter(
                            Transfers.TokenSymbol == token_symbol,
                            Transfers.BlockchainID == blockchain_id,
                            Transfers.IsSuccessful == True
                        ).first()
                        
                        temp_currency_id = f"{token_symbol.lower()}_{blockchain_name.lower().replace(' ', '_')}"
                        
                        currency = Currencies(
                            CurrencyID=temp_currency_id,
                            CurrencyName=token_symbol,
                            Symbol=token_symbol,
                            BlockchainID=blockchain_id,
                            SmartContractAddress=sample_transfer.TokenContract if sample_transfer else None,
                            IsToken=(sample_transfer.AssetType == 'token' if sample_transfer else True),
                            DecimalPlaces=18,  # پیش‌فرض برای اکثر توکن‌ها
                            CreatedAt=datetime.utcnow(),
                            UpdatedAt=datetime.utcnow()
                        )
                        session.add(currency)
                        session.flush()
                        logger.info(f"Created placeholder currency with ID {temp_currency_id}")
                
                # دریافت موجودی فعلی
                holding = session.query(UserHolding).filter(
                    UserHolding.UserID == user.UserID,
                    UserHolding.Symbol == token_symbol,
                    UserHolding.Blockchain == blockchain_name
                ).first()
                
                if holding:
                    if holding.Balance != balance:
                        logger.warning(f"Balance mismatch for {token_symbol}: Current={holding.Balance}, Calculated={balance}")
                        
                        # در حالت dry run فقط نمایش می‌دهیم
                        if not dry_run:
                            holding.Balance = balance
                            holding.UpdatedAt = datetime.utcnow()
                            holding.LastUpdated = datetime.utcnow()
                            logger.info(f"Updated balance for {token_symbol} to {balance}")
                    else:
                        logger.info(f"Balance for {token_symbol} is correct: {balance}")
                else:
                    logger.info(f"Creating new holding for {token_symbol} with balance {balance}")
                    
                    # در حالت dry run ایجاد نمی‌کنیم
                    if not dry_run and currency:
                        new_holding = UserHolding(
                            UserID=user.UserID,
                            CurrencyID=currency.CurrencyID,
                            Balance=balance,
                            Symbol=token_symbol,
                            Blockchain=blockchain_name,
                            IsToken=(currency.IsToken if currency else True),
                            CreatedAt=datetime.utcnow(),
                            UpdatedAt=datetime.utcnow(),
                            LastUpdated=datetime.utcnow()
                        )
                        session.add(new_holding)
                        logger.info(f"Created new holding for {token_symbol} with balance {balance}")
            
            # تعهد تغییرات برای این کاربر
            if not dry_run:
                session.commit()
                logger.info(f"Committed changes for user {user.UserID}")
            else:
                logger.info(f"Dry run - no changes committed for user {user.UserID}")
                session.rollback()
                
    except Exception as e:
        logger.error(f"Error rebuilding balances: {str(e)}", exc_info=True)
        session.rollback()
    finally:
        session.close()
        logger.info("Balance rebuild process completed")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rebuild user balances from transaction history")
    parser.add_argument("--user", help="Specific user ID to rebuild (omit for all users)")
    parser.add_argument("--force", action="store_true", help="Force delete existing balances")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    
    args = parser.parse_args()
    
    rebuild_user_balance(
        user_id=args.user,
        force=args.force,
        dry_run=not args.apply
    ) 