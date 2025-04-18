#!/usr/bin/env python3
"""
اسکریپت برای به روزرسانی کارمزد و وضعیت تراکنش‌های موجود در دیتابیس
این اسکریپت می‌تواند به صورت دستی اجرا شود تا تمام تراکنش‌های موجود در دیتابیس را بررسی و به روزرسانی کند.
"""

import os
import sys
import argparse
import time
from datetime import datetime, timedelta
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# اضافه کردن مسیر اصلی پروژه به سیستم
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# وارد کردن ماژول‌های مورد نیاز
from config import DATABASE_URL
from database.Transfers import Transfers
from database.Blockchains import Blockchains
from webhook.webhook_handler import update_transaction_fee_and_status, get_transaction_details_from_tatum, normalize_blockchain_name, logger

def parse_arguments():
    """پارس کردن آرگومان‌های ورودی خط فرمان"""
    parser = argparse.ArgumentParser(description='Update fees and status for existing transactions in the database')
    parser.add_argument('--days', type=int, default=7, help='Only process transactions from the last N days (default: 7)')
    parser.add_argument('--limit', type=int, default=100, help='Maximum number of transactions to process (default: 100)')
    parser.add_argument('--all', action='store_true', help='Process all transactions regardless of age')
    parser.add_argument('--force', action='store_true', help='Force update even for transactions that already have fee values')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without making changes')
    parser.add_argument('--blockchain', type=str, help='Only process transactions for a specific blockchain (e.g., ETH, TRX)')
    parser.add_argument('--status', type=str, choices=['pending', 'confirmed', 'failed'], help='Only process transactions with this status')
    return parser.parse_args()

def get_transactions_to_update(args):
    """دریافت لیست تراکنش‌هایی که باید به روزرسانی شوند"""
    logger.info("Getting list of transactions to update")
    
    try:
        # ایجاد اتصال به دیتابیس
        engine = create_engine(DATABASE_URL)
        
        with Session(engine) as session:
            # جستجوی بلاکچین مورد نظر (اگر تعیین شده باشد)
            blockchain_id = None
            if args.blockchain:
                blockchain_query = select(Blockchains.BlockchainID).where(
                    Blockchains.Symbol == args.blockchain.upper()
                )
                blockchain_result = session.execute(blockchain_query).first()
                if blockchain_result:
                    blockchain_id = blockchain_result[0]
                    logger.info(f"Found blockchain ID {blockchain_id} for symbol {args.blockchain}")
                else:
                    logger.warning(f"Blockchain with symbol {args.blockchain} not found")
                    return []
            
            # ساخت کوئری پایه
            query = select(
                Transfers.TxHash, 
                Transfers.BlockchainID, 
                Blockchains.Symbol.label('blockchain_symbol'),
                Transfers.Fee,
                Transfers.Status
            ).join(
                Blockchains, Transfers.BlockchainID == Blockchains.BlockchainID
            ).distinct()
            
            # اعمال فیلترها
            if not args.force:
                # اگر force نباشد، فقط تراکنش‌هایی که کارمزد ندارند بررسی شوند
                query = query.where(Transfers.Fee.is_(None))
            
            if not args.all:
                # اگر all نباشد، فقط تراکنش‌های n روز اخیر بررسی شوند
                cutoff_date = datetime.utcnow() - timedelta(days=args.days)
                query = query.where(Transfers.CreatedAt >= cutoff_date)
            
            if args.status:
                # اگر status تعیین شده باشد، فقط تراکنش‌های با آن وضعیت بررسی شوند
                query = query.where(Transfers.Status == args.status)
                
            if blockchain_id:
                # اگر blockchain تعیین شده باشد، فقط تراکنش‌های آن بلاکچین بررسی شوند
                query = query.where(Transfers.BlockchainID == blockchain_id)
            
            # اعمال محدودیت تعداد
            query = query.limit(args.limit)
            
            # اجرای کوئری
            results = session.execute(query).all()
            
            # تبدیل نتایج به لیست
            transactions = []
            for row in results:
                transactions.append({
                    'tx_hash': row.TxHash,
                    'blockchain_id': row.BlockchainID,
                    'blockchain_symbol': row.blockchain_symbol,
                    'current_fee': row.Fee,
                    'current_status': row.Status
                })
            
            logger.info(f"Found {len(transactions)} transactions to update")
            return transactions
    
    except Exception as e:
        logger.error(f"Error getting transactions to update: {str(e)}", exc_info=True)
        return []

def update_transactions(transactions, args):
    """به روزرسانی کارمزد و وضعیت تراکنش‌ها"""
    logger.info(f"Updating {len(transactions)} transactions")
    
    successful_updates = 0
    failed_updates = 0
    
    for idx, tx in enumerate(transactions):
        try:
            logger.info(f"Processing transaction {idx+1}/{len(transactions)}: {tx['tx_hash']}")
            
            if args.dry_run:
                logger.info(f"[DRY RUN] Would update transaction {tx['tx_hash']} on blockchain {tx['blockchain_symbol']}")
                continue
            
            # به روزرسانی کارمزد و وضعیت
            update_transaction_fee_and_status(tx['tx_hash'], tx['blockchain_symbol'])
            
            successful_updates += 1
            
            # استراحت کوتاه برای جلوگیری از فشار زیاد به API
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error updating transaction {tx['tx_hash']}: {str(e)}", exc_info=True)
            failed_updates += 1
    
    logger.info(f"Update complete: {successful_updates} successful, {failed_updates} failed")
    
    return successful_updates, failed_updates

def main():
    """تابع اصلی برنامه"""
    # پارس کردن آرگومان‌های ورودی
    args = parse_arguments()
    
    logger.info("Starting transaction fee and status update script")
    logger.info(f"Arguments: days={args.days}, limit={args.limit}, all={args.all}, force={args.force}, dry_run={args.dry_run}, blockchain={args.blockchain}, status={args.status}")
    
    # دریافت لیست تراکنش‌ها
    transactions = get_transactions_to_update(args)
    
    if not transactions:
        logger.info("No transactions found to update")
        return
    
    # به روزرسانی تراکنش‌ها
    successful, failed = update_transactions(transactions, args)
    
    logger.info(f"Script finished. Updated {successful} out of {len(transactions)} transactions")

if __name__ == "__main__":
    main() 