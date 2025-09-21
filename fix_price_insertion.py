#!/usr/bin/env python3
"""
اصلاح سیستم insert قیمت‌ها
Fix price insertion system to create historical records
"""

def fix_currency_price_service():
    """اصلاح فایل currency_price_service.py"""
    
    print("🔧 اصلاح سیستم insert قیمت‌ها...")
    
    # کد جایگزین برای ایجاد رکوردهای تاریخی
    replacement_code = '''
                                # بررسی آیا رکورد با همین timestamp وجود دارد
                                from datetime import datetime
                                current_timestamp = datetime.now()
                                
                                existing_price = session.query(Price).filter_by(
                                    crypto_id=currency_id, 
                                    currency=fiat,
                                    timestamp=current_timestamp  # بررسی timestamp دقیق
                                ).first()
                                
                                if existing_price:
                                    # اگر رکورد با همین timestamp وجود دارد، آپدیت کن
                                    logger.debug(f"Updating existing record for same timestamp: CurrencyID {currency_id} in {fiat}")
                                    existing_price.price = price_value
                                    existing_price.market_cap = market_cap_value
                                    existing_price.volume_24h = volume_24h_value
                                    existing_price.change_1h = change_1h_value
                                    existing_price.change_24h = change_24h_value
                                    existing_price.change_7d = change_7d_value
                                else:
                                    # همیشه رکورد جدید ایجاد کن با timestamp فعلی
                                    logger.debug(f"Creating new historical record for CurrencyID {currency_id} in {fiat}: {price_value}")
                                    new_price = Price(
                                        crypto_id=currency_id,
                                        currency=fiat,
                                        price=price_value,
                                        market_cap=market_cap_value,
                                        volume_24h=volume_24h_value,
                                        change_1h=change_1h_value,
                                        change_24h=change_24h_value,
                                        change_7d=change_7d_value,
                                        timestamp=current_timestamp,  # اضافه کردن timestamp
                                        is_historical=False  # رکورد فعلی
                                    )
                                    session.add(new_price)
    '''
    
    print("📝 کد جایگزین آماده شد")
    print("\n💡 برای اعمال تغییرات:")
    print("1. فایل Currencies/currency_price_service.py را باز کنید")
    print("2. خطوط 374-396 را با کد بالا جایگزین کنید")
    print("3. اطمینان حاصل کنید که timestamp برای هر رکورد جدید set شود")
    
    return replacement_code

def create_historical_price_inserter():
    """ایجاد کد جدید برای insert رکوردهای تاریخی"""
    
    code = '''
def insert_historical_price_record(session, currency_id, fiat, price_data, timestamp=None):
    """
    Insert a new historical price record
    اضافه کردن رکورد تاریخی جدید
    """
    from datetime import datetime
    from database.prices import Price
    
    if timestamp is None:
        timestamp = datetime.now()
    
    # همیشه رکورد جدید ایجاد کن (بدون بررسی existing)
    new_price = Price(
        crypto_id=currency_id,
        currency=fiat,
        price=price_data['price'],
        market_cap=price_data.get('market_cap'),
        volume_24h=price_data.get('volume_24h'),
        change_1h=price_data.get('change_1h'),
        change_24h=price_data.get('change_24h'),
        change_7d=price_data.get('change_7d'),
        timestamp=timestamp,
        is_historical=True,  # علامت‌گذاری به عنوان تاریخی
        last_updated=datetime.now()
    )
    
    session.add(new_price)
    return new_price

def get_hourly_price_updates():
    """
    دریافت قیمت‌ها و ذخیره به صورت ساعتی
    """
    from datetime import datetime, timedelta
    import time
    
    while True:
        try:
            current_time = datetime.now()
            
            # دریافت قیمت‌های جدید
            price_service = CurrencyPriceService()
            currencies = ['1', '16', '3']  # BTC, ETH, BNB
            
            for currency_id in currencies:
                # دریافت قیمت فعلی
                price_data = price_service.fetch_current_price(currency_id)
                
                if price_data:
                    # ذخیره رکورد جدید
                    session = Session(bind=engine)
                    try:
                        insert_historical_price_record(
                            session, 
                            currency_id, 
                            'USD', 
                            price_data, 
                            current_time
                        )
                        session.commit()
                        print(f"✅ رکورد جدید ذخیره شد: {currency_id} - ${price_data['price']}")
                        
                    except Exception as e:
                        session.rollback()
                        print(f"❌ خطا در ذخیره {currency_id}: {str(e)}")
                    finally:
                        session.close()
            
            # انتظار تا ساعت بعد
            time.sleep(3600)  # 1 ساعت
            
        except Exception as e:
            print(f"❌ خطا در چرخه اصلی: {str(e)}")
            time.sleep(300)  # 5 دقیقه در صورت خطا
    '''
    
    return code

def main():
    print("="*60)
    print("🛠️ اصلاح سیستم قیمت‌گذاری")
    print("="*60)
    
    # تشخیص مشکل
    print("❌ مشکل تشخیص داده شده:")
    print("   - کد فعلی رکوردهای موجود را آپدیت می‌کند")
    print("   - به جای ایجاد رکوردهای جدید")
    print("   - نتیجه: فقط یک رکورد برای هر ارز")
    print("   - عدم امکان ساخت چارت")
    
    # ارائه راه‌حل
    print(f"\n✅ راه‌حل:")
    print("   1. تغییر منطق از UPDATE به INSERT")
    print("   2. اضافه کردن timestamp منحصر به فرد")
    print("   3. علامت‌گذاری رکوردها به عنوان تاریخی")
    
    # تولید کدهای اصلاحی
    fix_code = fix_currency_price_service()
    historical_code = create_historical_price_inserter()
    
    # ذخیره کدهای اصلاحی
    with open('price_insertion_fix.py', 'w', encoding='utf-8') as f:
        f.write(f"""#!/usr/bin/env python3
# کد اصلاحی برای سیستم قیمت‌گذاری

# 1. کد جایگزین برای currency_price_service.py
{fix_code}

# 2. کد جدید برای insert رکوردهای تاریخی  
{historical_code}
""")
    
    print(f"\n💾 کدهای اصلاحی در فایل price_insertion_fix.py ذخیره شد")
    
    print(f"\n🔄 مراحل اعمال:")
    print("1. بک‌آپ از فایل currency_price_service.py")
    print("2. اعمال تغییرات در منطق insert/update")
    print("3. تست با چند رکورد")
    print("4. راه‌اندازی scheduler ساعتی")

if __name__ == "__main__":
    main()
