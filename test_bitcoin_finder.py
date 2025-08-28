#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست سریع برای Bitcoin Transaction Finder
"""

from bitcoin_transaction_finder import BitcoinTransactionFinder

def test_basic_functionality():
    """تست عملکرد پایه برنامه"""
    print("🧪 شروع تست Bitcoin Transaction Finder")
    print("-" * 40)
    
    # ایجاد نمونه
    finder = BitcoinTransactionFinder()
    
    # تست دریافت قیمت BTC
    print("1️⃣ تست دریافت قیمت BTC...")
    price = finder.get_btc_price()
    if price:
        print(f"   ✅ قیمت BTC: ${price:,.2f}")
    else:
        print("   ❌ خطا در دریافت قیمت")
        return False
    
    # تست دریافت بلاک‌های اخیر
    print("\n2️⃣ تست دریافت بلاک‌های اخیر...")
    blocks = finder.get_latest_blocks(5)
    if blocks:
        print(f"   ✅ {len(blocks)} بلاک دریافت شد")
        print(f"   🔗 آخرین بلاک: {blocks[0][:16]}...")
    else:
        print("   ❌ خطا در دریافت بلاک‌ها")
        return False
    
    # تست تجزیه تراکنش (با یک تراکنش از بلاک اول)
    print("\n3️⃣ تست دریافت تراکنش‌های بلاک...")
    if blocks:
        tx_hashes = finder.get_block_transactions(blocks[0])
        if tx_hashes:
            print(f"   ✅ {len(tx_hashes)} تراکنش در بلاک اول")
            
            # تست تجزیه یک تراکنش
            print("\n4️⃣ تست تجزیه تراکنش...")
            if len(tx_hashes) > 1:  # تراکنش اول معمولاً coinbase است
                tx_data = finder.get_transaction_details_mempool(tx_hashes[1])
                if tx_data:
                    analyzed = finder.analyze_transaction(tx_data)
                    if analyzed:
                        print(f"   ✅ تراکنش تجزیه شد: فی ${analyzed['fee_usd']:.2f}")
                    else:
                        print("   ⚠️ تراکنش تجزیه نشد (ممکن است صرافی باشد)")
                else:
                    print("   ❌ خطا در دریافت جزئیات تراکنش")
        else:
            print("   ❌ خطا در دریافت تراکنش‌ها")
    
    print("\n✅ تست‌ها تمام شد")
    return True

def test_small_search():
    """تست جستجوی کوچک"""
    print("\n🔍 تست جستجوی کوچک (5 تراکنش)")
    print("-" * 40)
    
    finder = BitcoinTransactionFinder()
    
    # جستجوی کوچک با تاریخ‌های شبیه‌سازی شده
    transactions = finder.find_transactions(
        target_fee_usd=50,  # هدف کوچک
        max_transactions=5  # تعداد کم
    )
    
    # نمایش تاریخ‌های شبیه‌سازی شده
    if transactions:
        print("\n📅 نمونه تاریخ‌های شبیه‌سازی شده:")
        for i, tx in enumerate(transactions[:3]):
            print(f"  {i+1}. تاریخ شبیه‌سازی: {tx['transaction_date']}")
            print(f"      تاریخ واقعی: {tx['actual_date']}")
    
    if transactions:
        finder.print_summary(transactions)
        return True
    else:
        print("❌ هیچ تراکنشی یافت نشد")
        return False

if __name__ == "__main__":
    print("🚀 شروع تست‌های Bitcoin Transaction Finder")
    print("=" * 50)
    
    # تست عملکرد پایه
    if test_basic_functionality():
        # تست جستجوی کوچک
        test_small_search()
    
    print("\n🏁 تست‌ها به پایان رسید")
