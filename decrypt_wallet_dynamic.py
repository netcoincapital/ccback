#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
from Crypto.Cipher import AES
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# اضافه کردن مسیر پروژه
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# AES encryption key
AES_SECRET_KEY = os.environ.get('AES_SECRET_KEY', 'MySecretKey@1234')

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+mysqlconnector://coincee:09387270277Mn!!??@localhost/coincee")

def decrypt_mnemonic_aes(encrypted_mnemonic: str) -> str:
    """رمزگشایی عبارت بازیابی با AES-GCM"""
    try:
        data = base64.b64decode(encrypted_mnemonic)
        salt = data[:16]
        nonce = data[16:32]
        tag = data[32:48]
        ciphertext = data[48:]
        
        secret_key_bytes = AES_SECRET_KEY.encode('utf-8')
        cipher = AES.new(secret_key_bytes, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        # حذف salt از ابتدای متن
        return plaintext[16:].decode('utf-8')
    except Exception as e:
        raise ValueError(f"Failed to decrypt mnemonic: {str(e)}")

def decrypt_private_key_aes(encrypted_key: str) -> str:
    """رمزگشایی کلید خصوصی با AES-GCM"""
    try:
        data = base64.b64decode(encrypted_key)
        nonce = data[:16]
        tag = data[16:32]
        ciphertext = data[32:]
        
        secret_key_bytes = AES_SECRET_KEY.encode()
        cipher = AES.new(secret_key_bytes, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext.decode()
    except Exception as e:
        raise ValueError(f"Failed to decrypt private key: {str(e)}")

def get_wallet_data(wallet_id=None, address=None, limit=None):
    """دریافت داده‌های کیف پول از دیتابیس"""
    try:
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        if wallet_id:
            # جستجو با wallet ID
            query = text("""
                SELECT w.WalletID, a.PhraseKey, 
                       a.AddressID, a.PublicAddress, a.PrivateKey, a.BlockchainID
                FROM wallets w
                JOIN address a ON w.WalletID = a.WalletID
                WHERE w.WalletID = :wallet_id
            """)
            result = session.execute(query, {"wallet_id": wallet_id}).fetchall()
            
        elif address:
            # جستجو با آدرس
            query = text("""
                SELECT w.WalletID, a.PhraseKey, 
                       a.AddressID, a.PublicAddress, a.PrivateKey, a.BlockchainID
                FROM wallets w
                JOIN address a ON w.WalletID = a.WalletID
                WHERE a.PublicAddress = :address
            """)
            result = session.execute(query, {"address": address}).fetchall()
            
        else:
            # لیست همه کیف پول‌ها
            query = text("""
                SELECT w.WalletID, a.PhraseKey, 
                       a.AddressID, a.PublicAddress, a.PrivateKey, a.BlockchainID
                FROM wallets w
                JOIN address a ON w.WalletID = a.WalletID
                ORDER BY w.WalletID
            """)
            if limit:
                query = text(str(query) + f" LIMIT {limit}")
            result = session.execute(query).fetchall()
        
        session.close()
        return result
        
    except Exception as e:
        print(f"❌ خطا در اتصال به دیتابیس: {str(e)}")
        return []

def decrypt_wallet(wallet_data):
    """رمزگشایی یک کیف پول"""
    wallet_id, phrase_key, address_id, public_address, private_key, blockchain_id = wallet_data
    
    print(f"\n{'='*80}")
    print(f"🔐 رمزگشایی کیف پول")
    print(f"{'='*80}")
    print(f"🆔 Wallet ID: {wallet_id}")
    print(f"🏠 Address ID: {address_id}")
    print(f"🔗 Address: {public_address}")
    print(f"⛓️  Blockchain ID: {blockchain_id}")
    print("-" * 80)
    
    try:
        # رمزگشایی عبارت ۱۲ کلمه‌ای
        if phrase_key:
            # بررسی اینکه آیا PhraseKey رمزگذاری شده است یا خیر
            if len(phrase_key) > 100:  # احتمالاً رمزگذاری شده
                decrypted_phrase = decrypt_mnemonic_aes(phrase_key)
            else:
                # احتمالاً متن ساده است
                decrypted_phrase = phrase_key
            
            print(f"🔓 عبارت ۱۲ کلمه‌ای:")
            print(f"📝 {decrypted_phrase}")
            
            # تأیید تعداد کلمات
            words = decrypted_phrase.split()
            print(f"📊 تعداد کلمات: {len(words)}")
            
            if len(words) == 12:
                print("✅ تأیید: عبارت شامل ۱۲ کلمه است")
            else:
                print(f"⚠️ هشدار: تعداد کلمات {len(words)} است، نه ۱۲")
        else:
            print("⚠️ عبارت بازیابی یافت نشد")
            decrypted_phrase = None
        
        # رمزگشایی کلید خصوصی
        if private_key:
            # بررسی اینکه آیا PrivateKey رمزگذاری شده است یا خیر
            if len(private_key) > 100:  # احتمالاً رمزگذاری شده
                decrypted_private_key = decrypt_private_key_aes(private_key)
            else:
                # احتمالاً متن ساده است
                decrypted_private_key = private_key
            
            print(f"🔑 کلید خصوصی:")
            print(f"🔓 {decrypted_private_key}")
        else:
            print("⚠️ کلید خصوصی یافت نشد")
            decrypted_private_key = None
        
        print("✅ عملیات موفقیت‌آمیز بود!")
        return {
            'wallet_id': wallet_id,
            'address': public_address,
            'mnemonic': decrypted_phrase,
            'private_key': decrypted_private_key
        }
        
    except Exception as e:
        print(f"❌ خطا در رمزگشایی: {str(e)}")
        return None

def main():
    """تابع اصلی"""
    print("🚀 ابزار رمزگشایی کیف پول‌های پویا")
    print("="*80)
    
    # بررسی آرگومان‌های خط فرمان
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("""
📚 راهنمای استفاده:

1️⃣ رمزگشایی یک کیف پول با Wallet ID:
   python decrypt_wallet_dynamic.py --wallet-id WALLET_ID

2️⃣ رمزگشایی یک کیف پول با آدرس:
   python decrypt_wallet_dynamic.py --address ADDRESS

3️⃣ لیست تمام کیف پول‌ها (اولین 10 تا):
   python decrypt_wallet_dynamic.py --list

4️⃣ لیست تعداد مشخصی از کیف پول‌ها:
   python decrypt_wallet_dynamic.py --list --limit 5

مثال‌ها:
- python decrypt_wallet_dynamic.py --wallet-id acfbe766-0f0a-4a9f-9010-6c2eaf547f61
- python decrypt_wallet_dynamic.py --address TYvLGvjy62W8j9oMHZRpsKyrafGAxWBf2K
- python decrypt_wallet_dynamic.py --list --limit 3
            """)
            return
        
        elif sys.argv[1] == "--wallet-id" and len(sys.argv) > 2:
            wallet_id = sys.argv[2]
            print(f"🔍 جستجو برای Wallet ID: {wallet_id}")
            wallet_data_list = get_wallet_data(wallet_id=wallet_id)
            
        elif sys.argv[1] == "--address" and len(sys.argv) > 2:
            address = sys.argv[2]
            print(f"🔍 جستجو برای آدرس: {address}")
            wallet_data_list = get_wallet_data(address=address)
            
        elif sys.argv[1] == "--list":
            limit = 10  # پیش‌فرض
            if len(sys.argv) > 3 and sys.argv[2] == "--limit":
                limit = int(sys.argv[3])
            print(f"📋 لیست {limit} کیف پول اول:")
            wallet_data_list = get_wallet_data(limit=limit)
            
        else:
            print("❌ آرگومان نامعتبر. از --help استفاده کنید.")
            return
    else:
        # حالت پیش‌فرض: نمایش اولین 5 کیف پول
        print("📋 نمایش اولین 5 کیف پول:")
        wallet_data_list = get_wallet_data(limit=5)
    
    if not wallet_data_list:
        print("❌ هیچ کیف پولی یافت نشد.")
        return
    
    print(f"✅ {len(wallet_data_list)} کیف پول یافت شد.")
    
    results = []
    for wallet_data in wallet_data_list:
        result = decrypt_wallet(wallet_data)
        if result:
            results.append(result)
    
    print(f"\n{'='*80}")
    print(f"📊 خلاصه نتایج: {len(results)} کیف پول با موفقیت رمزگشایی شد")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()