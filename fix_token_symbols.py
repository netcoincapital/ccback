#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from decimal import Decimal

# اضافه کردن مسیر پروژه
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+mysqlconnector://coincee:09387270277Mn!!??@localhost/coincee")

def fix_token_symbols():
    """اصلاح سیمبل‌های توکن در جدول transfers"""
    print("🔧 شروع اصلاح سیمبل‌های توکن...")
    
    try:
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # یافتن تراکنش‌هایی که TokenSymbol آدرس قرارداد است
        find_contract_symbols_query = text("""
            SELECT TransferID, TokenSymbol, TokenContract, BlockchainID
            FROM transfers 
            WHERE TokenSymbol LIKE '0x%' 
            AND LENGTH(TokenSymbol) >= 10
            ORDER BY TransferID
        """)
        
        results = session.execute(find_contract_symbols_query).fetchall()
        print(f"📊 {len(results)} تراکنش با سیمبل آدرس قرارداد پیدا شد")
        
        if not results:
            print("✅ هیچ تراکنشی برای اصلاح پیدا نشد")
            return
        
        fixed_count = 0
        
        for transfer_id, token_symbol, token_contract, blockchain_id in results:
            print(f"\n🔍 پردازش تراکنش {transfer_id}:")
            print(f"   TokenSymbol فعلی: {token_symbol}")
            print(f"   TokenContract: {token_contract}")
            
            # جستجو برای سیمبل واقعی در جدول currencies
            actual_symbol = None
            
            # روش 1: جستجو با آدرس کامل TokenContract
            if token_contract:
                symbol_query = text("""
                    SELECT Symbol FROM currencies 
                    WHERE LOWER(SmartContractAddress) = LOWER(:contract_address)
                    AND BlockchainID = :blockchain_id
                    LIMIT 1
                """)
                
                result = session.execute(symbol_query, {
                    'contract_address': token_contract,
                    'blockchain_id': blockchain_id
                }).fetchone()
                
                if result:
                    actual_symbol = result[0]
                    print(f"   ✅ سیمبل واقعی پیدا شد (TokenContract): {actual_symbol}")
            
            # روش 2: جستجو با TokenSymbol (آدرس کوتاه شده)
            if not actual_symbol:
                symbol_query2 = text("""
                    SELECT Symbol FROM currencies 
                    WHERE LOWER(SmartContractAddress) LIKE CONCAT('%', LOWER(:token_symbol), '%')
                    AND BlockchainID = :blockchain_id
                    LIMIT 1
                """)
                
                result2 = session.execute(symbol_query2, {
                    'token_symbol': token_symbol,
                    'blockchain_id': blockchain_id
                }).fetchone()
                
                if result2:
                    actual_symbol = result2[0]
                    print(f"   ✅ سیمبل واقعی پیدا شد (fuzzy match): {actual_symbol}")
            
            # روش 3: توکن‌های خاص شناخته شده
            if not actual_symbol:
                known_tokens = {
                    '0x55d398326f99059ff775485246999027b3197955': 'USDT',  # USDT on BSC
                    '0x55d398326f99059ff7': 'USDT',  # USDT کوتاه شده
                    '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c': 'WBNB', # WBNB on BSC
                    'T9yYp7JUxypLk7GFhsLRj5jN6ZrNDcH2Cf': 'NCC',        # NCC on Tron
                    'TCDgp5bwtixaShPifUm7HpZ71C1pe6zif1': 'NCC'         # NCC on Tron
                }
                
                # بررسی TokenContract
                if token_contract and token_contract.lower() in [k.lower() for k in known_tokens.keys()]:
                    for addr, symbol in known_tokens.items():
                        if addr.lower() == token_contract.lower():
                            actual_symbol = symbol
                            print(f"   ✅ سیمبل از توکن‌های شناخته شده: {actual_symbol}")
                            break
                
                # بررسی TokenSymbol
                if not actual_symbol and token_symbol.lower() in [k.lower() for k in known_tokens.keys()]:
                    for addr, symbol in known_tokens.items():
                        if addr.lower() == token_symbol.lower():
                            actual_symbol = symbol
                            print(f"   ✅ سیمبل از توکن‌های شناخته شده: {actual_symbol}")
                            break
            
            # اگر سیمبل واقعی پیدا شد، به‌روزرسانی کن
            if actual_symbol and actual_symbol != token_symbol:
                update_query = text("""
                    UPDATE transfers 
                    SET TokenSymbol = :new_symbol 
                    WHERE TransferID = :transfer_id
                """)
                
                session.execute(update_query, {
                    'new_symbol': actual_symbol,
                    'transfer_id': transfer_id
                })
                
                print(f"   🔄 به‌روزرسانی شد: {token_symbol} → {actual_symbol}")
                fixed_count += 1
            else:
                if actual_symbol:
                    print(f"   ⚠️ سیمبل تغییری نکرد: {actual_symbol}")
                else:
                    print(f"   ❌ سیمبل واقعی پیدا نشد، به UNKNOWN تغییر می‌یابد")
                    
                    update_query = text("""
                        UPDATE transfers 
                        SET TokenSymbol = 'UNKNOWN' 
                        WHERE TransferID = :transfer_id
                    """)
                    
                    session.execute(update_query, {
                        'transfer_id': transfer_id
                    })
                    fixed_count += 1
        
        # کامیت تغییرات
        session.commit()
        print(f"\n✅ {fixed_count} تراکنش با موفقیت اصلاح شد!")
        
        # نمایش نتایج نهایی
        final_check_query = text("""
            SELECT TokenSymbol, COUNT(*) as count
            FROM transfers 
            GROUP BY TokenSymbol
            ORDER BY count DESC
        """)
        
        final_results = session.execute(final_check_query).fetchall()
        print(f"\n📊 خلاصه سیمبل‌های موجود:")
        for symbol, count in final_results:
            print(f"   {symbol}: {count} تراکنش")
        
        session.close()
        
    except Exception as e:
        print(f"❌ خطا در اصلاح سیمبل‌ها: {str(e)}")

def rebuild_user_holdings():
    """بازسازی جدول userholding بر اساس تراکنش‌های اصلاح شده"""
    print("\n🔄 شروع بازسازی موجودی‌های کاربران...")
    
    try:
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # حذف موجودی‌های اشتباه (BNB با موجودی صفر)
        delete_query = text("""
            DELETE FROM userholding 
            WHERE Symbol = 'BNB' AND Balance = 0
            AND HoldingID IN (1425)  -- فقط رکورد مشکل‌دار
        """)
        
        deleted = session.execute(delete_query).rowcount
        print(f"🗑️ {deleted} رکورد اشتباه حذف شد")
        
        # بازسازی موجودی بر اساس تراکنش‌های USDT
        usdt_transfers_query = text("""
            SELECT 
                w.UserID,
                t.TokenSymbol,
                t.BlockchainID,
                b.BlockchainName,
                SUM(CASE WHEN t.Direction = 'inbound' THEN t.Amount ELSE -t.Amount END) as total_balance
            FROM transfers t
            JOIN address a ON t.AddressID = a.AddressID
            JOIN wallets w ON a.WalletID = w.WalletID  
            JOIN blockchains b ON t.BlockchainID = b.BlockchainID
            WHERE t.TokenSymbol = 'USDT' 
            AND t.IsSuccessful = 1
            GROUP BY w.UserID, t.TokenSymbol, t.BlockchainID, b.BlockchainName
            HAVING total_balance > 0
        """)
        
        usdt_results = session.execute(usdt_transfers_query).fetchall()
        print(f"📊 {len(usdt_results)} موجودی USDT پیدا شد برای بازسازی")
        
        for user_id, token_symbol, blockchain_id, blockchain_name, total_balance in usdt_results:
            print(f"   کاربر {user_id}: {total_balance} {token_symbol} در {blockchain_name}")
            
            # بررسی وجود رکورد موجودی
            existing_query = text("""
                SELECT HoldingID FROM userholding 
                WHERE UserID = :user_id 
                AND Symbol = :symbol 
                AND Blockchain = :blockchain
            """)
            
            existing = session.execute(existing_query, {
                'user_id': user_id,
                'symbol': token_symbol,
                'blockchain': blockchain_name
            }).fetchone()
            
            if existing:
                # به‌روزرسانی موجودی موجود
                update_holding_query = text("""
                    UPDATE userholding 
                    SET Balance = :balance, UpdatedAt = NOW(), LastUpdated = NOW()
                    WHERE HoldingID = :holding_id
                """)
                
                session.execute(update_holding_query, {
                    'balance': str(total_balance),
                    'holding_id': existing[0]
                })
                print(f"   ✅ موجودی به‌روزرسانی شد")
            else:
                # ایجاد موجودی جدید
                insert_holding_query = text("""
                    INSERT INTO userholding 
                    (UserID, CurrencyID, Balance, Symbol, Blockchain, IsToken, CreatedAt, UpdatedAt, LastUpdated)
                    VALUES 
                    (:user_id, :currency_id, :balance, :symbol, :blockchain, 1, NOW(), NOW(), NOW())
                """)
                
                # تولید CurrencyID موقت
                temp_currency_id = f"{token_symbol.lower()}_{blockchain_name.lower().replace(' ', '_')}"
                
                session.execute(insert_holding_query, {
                    'user_id': user_id,
                    'currency_id': temp_currency_id,
                    'balance': str(total_balance),
                    'symbol': token_symbol,
                    'blockchain': blockchain_name
                })
                print(f"   ✅ موجودی جدید ایجاد شد")
        
        session.commit()
        print("✅ بازسازی موجودی‌ها کامل شد!")
        session.close()
        
    except Exception as e:
        print(f"❌ خطا در بازسازی موجودی‌ها: {str(e)}")

def main():
    """تابع اصلی"""
    print("🚀 ابزار اصلاح سیمبل‌های توکن و موجودی‌های کاربران")
    print("="*70)
    
    # مرحله 1: اصلاح سیمبل‌های توکن
    fix_token_symbols()
    
    # مرحله 2: بازسازی موجودی‌های کاربران
    rebuild_user_holdings()
    
    print("\n" + "="*70)
    print("✅ همه مراحل تکمیل شد!")
    print("📋 برای بررسی نتایج:")
    print("   SELECT * FROM transfers WHERE TokenSymbol = 'USDT';")
    print("   SELECT * FROM userholding WHERE Symbol = 'USDT';")

if __name__ == "__main__":
    main()