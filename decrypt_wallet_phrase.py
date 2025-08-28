#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from sqlalchemy import create_engine, Column, String, Integer, Boolean, TIMESTAMP, ForeignKey, TEXT, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import base64
from Crypto.Cipher import AES
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_USER = os.getenv('DB_USER', 'coinceeper')
DB_PASSWORD = os.getenv('DB_PASSWORD', '09387270277Mn!!??')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'coinceeper')

# AES encryption key
AES_SECRET_KEY = os.environ.get('AES_SECRET_KEY', 'MySecretKey@1234')

# Create base class for models
Base = declarative_base()

# Database models
class Wallets(Base):
    __tablename__ = 'wallets'
    WalletID = Column(String(50), primary_key=True)
    UserID = Column(String(36), ForeignKey('users.UserID', ondelete='CASCADE'), nullable=False)
    IsMultiSig = Column(Boolean, default=False, nullable=False)
    RequiredSignatures = Column(String(10), nullable=False)
    CreatedAt = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False)
    UpdatedAt = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class Address(Base):
    __tablename__ = 'address'
    AddressID = Column(Integer, primary_key=True, autoincrement=True)
    WalletID = Column(String(50), ForeignKey('wallets.WalletID'), nullable=False)
    BlockchainID = Column(Integer, ForeignKey('blockchains.BlockchainID'), nullable=False)
    PublicAddress = Column(String(255), nullable=False)
    PrivateKey = Column(TEXT, nullable=True)
    PhraseKey = Column(TEXT, nullable=True)
    CreatedAt = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    __table_args__ = (Index('ix_public_address', 'PublicAddress'),)

class Blockchains(Base):
    __tablename__ = 'blockchains'
    BlockchainID = Column(Integer, primary_key=True, autoincrement=True)
    BlockchainName = Column(String(100), nullable=False, unique=True)
    Symbol = Column(String(50), nullable=False)
    ChainCode = Column(String(100), nullable=False)
    CreatedAt = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    UpdatedAt = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# Decryption function
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

def create_database_connection():
    """ایجاد اتصال به دیتابیس"""
    try:
        # Try MySQL first with provided credentials
        DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
        print(f"🔗 تلاش برای اتصال به MySQL: {DB_HOST}/{DB_NAME}")
        
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return SessionLocal
    except Exception as e:
        print(f"❌ خطا در اتصال به دیتابیس: {str(e)}")
        return None

def find_and_decrypt_wallet_phrase(public_address: str):
    """
    یافتن کیف پول از روی آدرس عمومی و رمزگشایی عبارت ۱۲ کلمه‌ای
    """
    SessionLocal = create_database_connection()
    if not SessionLocal:
        return None
    
    session = SessionLocal()
    
    try:
        print(f"🔍 جستجو برای آدرس: {public_address}")
        
        # جستجو برای آدرس در دیتابیس
        address_record = session.query(Address).filter(
            Address.PublicAddress == public_address
        ).first()
        
        if not address_record:
            print(f"❌ آدرس {public_address} در دیتابیس یافت نشد!")
            return None
        
        print(f"✅ آدرس پیدا شد!")
        print(f"📝 Address ID: {address_record.AddressID}")
        print(f"🔗 Wallet ID: {address_record.WalletID}")
        
        # دریافت اطلاعات کیف پول
        wallet_record = session.query(Wallets).filter(
            Wallets.WalletID == address_record.WalletID
        ).first()
        
        if wallet_record:
            print(f"👤 User ID: {wallet_record.UserID}")
            print(f"🔐 Multi-Sig: {wallet_record.IsMultiSig}")
        
        # دریافت اطلاعات بلاکچین
        blockchain_record = session.query(Blockchains).filter(
            Blockchains.BlockchainID == address_record.BlockchainID
        ).first()
        
        if blockchain_record:
            print(f"⛓️ Blockchain: {blockchain_record.BlockchainName} ({blockchain_record.Symbol})")
        
        # بررسی وجود عبارت رمزنگاری شده
        if not address_record.PhraseKey:
            print("❌ عبارت ۱۲ کلمه‌ای رمزنگاری شده برای این آدرس یافت نشد!")
            return None
        
        print(f"🔒 عبارت رمزنگاری شده یافت شد")
        print(f"📏 طول داده رمزنگاری شده: {len(address_record.PhraseKey)} کاراکتر")
        
        # رمزگشایی عبارت ۱۲ کلمه‌ای
        try:
            decrypted_phrase = decrypt_mnemonic_aes(address_record.PhraseKey)
            
            print("\n" + "="*60)
            print("🔓 عبارت ۱۲ کلمه‌ای رمزگشایی شده:")
            print("="*60)
            print(f"📝 {decrypted_phrase}")
            print("="*60)
            
            # تأیید تعداد کلمات
            words = decrypted_phrase.split()
            print(f"📊 تعداد کلمات: {len(words)}")
            
            if len(words) == 12:
                print("✅ تأیید: عبارت شامل ۱۲ کلمه است")
                for i, word in enumerate(words, 1):
                    print(f"  {i:2}. {word}")
            else:
                print(f"⚠️ هشدار: تعداد کلمات {len(words)} است، نه ۱۲")
            
            # نمایش کلید خصوصی هم اگر موجود باشد
            if address_record.PrivateKey:
                print(f"\n🔑 کلید خصوصی موجود است (طول: {len(address_record.PrivateKey)} کاراکتر)")
                try:
                    from security.encryption import decrypt_private_key_aes
                    decrypted_private_key = decrypt_private_key_aes(address_record.PrivateKey)
                    print(f"🔓 کلید خصوصی: {decrypted_private_key[:10]}...{decrypted_private_key[-10:]}")
                except:
                    print("⚠️ خطا در رمزگشایی کلید خصوصی")
                
            return decrypted_phrase
            
        except Exception as e:
            print(f"❌ خطا در رمزگشایی: {str(e)}")
            return None
    
    except Exception as e:
        print(f"❌ خطا در دسترسی به دیتابیس: {str(e)}")
        return None
    
    finally:
        session.close()

def main():
    """تابع اصلی"""
    target_address = "TN5DDkGuc25V44wjNEuQqcwP2yAxNtCwJg"
    
    print("🚀 شروع عملیات یافتن و رمزگشایی کیف پول")
    print(f"🎯 آدرس هدف: {target_address}")
    print("-" * 60)
    
    result = find_and_decrypt_wallet_phrase(target_address)
    
    if result:
        print("\n✅ عملیات با موفقیت انجام شد!")
    else:
        print("\n❌ عملیات ناموفق بود!")

if __name__ == "__main__":
    main() 