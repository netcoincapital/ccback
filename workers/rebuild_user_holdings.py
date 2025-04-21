import sys
import os
import logging
import argparse
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import func

# Add the parent directory to the sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, Users, Wallets, Address, Transfers, UserHolding, Blockchains, Currencies
from services.balance_service import BalanceService
from utils.logging_config import setup_logging, get_logger

# Configure logging
logger = get_logger(__name__)

def rebuild_user_holdings(user_id=None, days_back=None, force_rebuild=False):
    """
    بازسازی دارایی‌های کاربر بر اساس تراکنش‌های ثبت شده
    
    Args:
        user_id (str, optional): شناسه کاربر برای بازسازی دارایی‌های یک کاربر خاص
        days_back (int, optional): تعداد روزهایی که تراکنش‌ها بررسی شوند
        force_rebuild (bool): اگر True باشد، تمامی دارایی‌ها از صفر بازسازی می‌شوند
    """
    logger.info(f"Starting holdings rebuild process for {'user ' + user_id if user_id else 'all users'}")
    
    session = SessionLocal()
    try:
        # ایجاد سرویس موجودی
        balance_service = BalanceService(session)
        
        # تعیین کاربران مورد نظر
        if user_id:
            users = session.query(Users).filter(Users.UserID == user_id).all()
            if not users:
                logger.warning(f"User with ID {user_id} not found")
                return
        else:
            users = session.query(Users).all()
            
        logger.info(f"Processing {len(users)} users")
        
        # تعیین محدوده زمانی برای تراکنش‌ها
        timestamp_filter = None
        if days_back:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            timestamp_filter = Transfers.Timestamp >= cutoff_date
            logger.info(f"Looking at transfers from {cutoff_date} onwards")
        
        # پردازش هر کاربر
        for user in users:
            logger.info(f"Processing user {user.UserID}")
            
            # دریافت کیف پول‌های کاربر
            wallets = session.query(Wallets).filter(Wallets.UserID == user.UserID).all()
            if not wallets:
                logger.warning(f"No wallets found for user {user.UserID}")
                continue
                
            wallet_ids = [wallet.WalletID for wallet in wallets]
            logger.info(f"Found {len(wallets)} wallets for user {user.UserID}")
            
            # اگر بازسازی کامل درخواست شده، دارایی‌های کاربر را پاک کنیم
            if force_rebuild:
                holdings_count = session.query(UserHolding).filter(UserHolding.UserID == user.UserID).count()
                logger.info(f"Deleting {holdings_count} existing holdings for user {user.UserID}")
                session.query(UserHolding).filter(UserHolding.UserID == user.UserID).delete()
                session.commit()
            
            # دریافت تمامی تراکنش‌های مربوط به کاربر
            query = session.query(Transfers).filter(Transfers.WalletID.in_(wallet_ids))
            
            # اعمال فیلتر زمانی اگر مشخص شده باشد
            if timestamp_filter:
                query = query.filter(timestamp_filter)
                
            # مرتب‌سازی بر اساس زمان برای اطمینان از صحت توالی
            transfers = query.order_by(Transfers.Timestamp).all()
            
            logger.info(f"Found {len(transfers)} transfers for user {user.UserID}")
            
            # اعمال هر تراکنش به موجودی کاربر
            applied_count = 0
            for transfer in transfers:
                if transfer.IsSuccessful:
                    success = balance_service.apply_transfer_to_user_holding(transfer)
                    if success:
                        applied_count += 1
            
            logger.info(f"Applied {applied_count} transfers for user {user.UserID}")
            
            # اطمینان از وجود دارایی‌ها برای تمامی توکن‌های دریافتی
            # که ممکن است در transfers وجود داشته باشند اما در userholding نباشند
            _ensure_all_tokens_registered(session, user.UserID, wallet_ids)
            
    except Exception as e:
        logger.error(f"Error rebuilding holdings: {str(e)}", exc_info=True)
        session.rollback()
    finally:
        session.close()
        
def _ensure_all_tokens_registered(session, user_id, wallet_ids):
    """
    اطمینان از اینکه برای همه توکن‌های دریافتی، رکورد متناظر در جدول UserHolding وجود دارد
    
    Args:
        session: نشست دیتابیس
        user_id: شناسه کاربر
        wallet_ids: لیست شناسه‌های کیف پول‌های کاربر
    """
    try:
        # یافتن همه توکن‌های منحصر به فرد که کاربر دریافت کرده
        # فقط تراکنش‌های دریافتی و موفق را در نظر می‌گیریم
        unique_tokens = session.query(
            Transfers.TokenSymbol,
            Transfers.TokenContract,
            Transfers.BlockchainID,
            Transfers.AssetType
        ).filter(
            Transfers.WalletID.in_(wallet_ids),
            Transfers.Direction == 'inbound',
            Transfers.IsSuccessful == True
        ).distinct().all()
        
        for token in unique_tokens:
            if not token.TokenSymbol:
                continue
                
            # یافتن بلاکچین مربوطه
            blockchain = session.query(Blockchains).filter(
                Blockchains.BlockchainID == token.BlockchainID
            ).first()
            
            if not blockchain:
                logger.warning(f"Blockchain ID {token.BlockchainID} not found")
                continue
                
            # بررسی وجود رکورد دارایی برای این توکن
            holding = session.query(UserHolding).filter(
                UserHolding.UserID == user_id,
                UserHolding.Symbol == token.TokenSymbol,
                UserHolding.Blockchain == blockchain.BlockchainName
            ).first()
            
            if not holding:
                logger.info(f"Creating missing holding record for {token.TokenSymbol} on {blockchain.BlockchainName}")
                
                # یافتن یا ایجاد کارنسی
                currency = session.query(Currencies).filter(
                    Currencies.Symbol == token.TokenSymbol,
                    Currencies.BlockchainID == token.BlockchainID
                ).first()
                
                if not currency:
                    temp_currency_id = f"{token.TokenSymbol.lower()}_{blockchain.BlockchainName.lower().replace(' ', '_')}"
                    logger.info(f"Creating missing currency record with ID {temp_currency_id}")
                    
                    currency = Currencies(
                        CurrencyID=temp_currency_id,
                        CurrencyName=token.TokenSymbol,
                        Symbol=token.TokenSymbol,
                        BlockchainID=token.BlockchainID,
                        SmartContractAddress=token.TokenContract,
                        IsToken=(token.AssetType == 'token'),
                        DecimalPlaces=18,  # پیش‌فرض برای اکثر توکن‌ها
                        CreatedAt=datetime.utcnow(),
                        UpdatedAt=datetime.utcnow()
                    )
                    session.add(currency)
                    session.flush()
                
                # محاسبه موجودی از تراکنش‌ها
                inbound_sum = session.query(func.sum(Transfers.Amount)).filter(
                    Transfers.WalletID.in_(wallet_ids),
                    Transfers.TokenSymbol == token.TokenSymbol,
                    Transfers.BlockchainID == token.BlockchainID,
                    Transfers.Direction == 'inbound',
                    Transfers.IsSuccessful == True
                ).scalar() or Decimal('0')
                
                outbound_sum = session.query(func.sum(Transfers.Amount)).filter(
                    Transfers.WalletID.in_(wallet_ids),
                    Transfers.TokenSymbol == token.TokenSymbol,
                    Transfers.BlockchainID == token.BlockchainID,
                    Transfers.Direction == 'outbound',
                    Transfers.IsSuccessful == True
                ).scalar() or Decimal('0')
                
                balance = max(inbound_sum - outbound_sum, Decimal('0'))
                
                # ایجاد رکورد دارایی
                new_holding = UserHolding(
                    UserID=user_id,
                    CurrencyID=currency.CurrencyID,
                    Balance=balance,
                    Symbol=token.TokenSymbol,
                    Blockchain=blockchain.BlockchainName,
                    IsToken=(token.AssetType == 'token'),
                    CreatedAt=datetime.utcnow(),
                    UpdatedAt=datetime.utcnow(),
                    LastUpdated=datetime.utcnow()
                )
                session.add(new_holding)
                
                # ذخیره تغییرات
                session.commit()
                logger.info(f"Created new holding with balance {balance} for {token.TokenSymbol} on {blockchain.BlockchainName}")
                
    except Exception as e:
        logger.error(f"Error ensuring token registrations: {str(e)}", exc_info=True)
        session.rollback()

if __name__ == "__main__":
    # تنظیم logging
    setup_logging()
    
    # پارس آرگومان‌های خط فرمان
    parser = argparse.ArgumentParser(description='بازسازی دارایی‌های کاربر بر اساس تراکنش‌ها')
    parser.add_argument('--user-id', help='شناسه کاربر برای بازسازی دارایی‌های یک کاربر خاص')
    parser.add_argument('--days', type=int, help='بازسازی تراکنش‌های N روز اخیر')
    parser.add_argument('--force', action='store_true', help='بازسازی کامل دارایی‌ها از صفر')
    
    args = parser.parse_args()
    
    rebuild_user_holdings(user_id=args.user_id, days_back=args.days, force_rebuild=args.force) 