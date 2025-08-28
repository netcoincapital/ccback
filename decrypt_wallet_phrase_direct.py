#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
from Crypto.Cipher import AES
import os

# AES encryption key
AES_SECRET_KEY = os.environ.get('AES_SECRET_KEY', 'MySecretKey@1234')

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

def main():
    """تابع اصلی"""
    target_address = "TN5DDkGuc25V44wjNEuQqcwP2yAxNtCwJg"
    
    # داده‌های یافت شده از فایل SQL
    encrypted_phrase_key = "8KzesiSnZjG9gC4tUP2eyxYxrZijWFN1nrMyfGKTilr0vQnUnxP06tLb7Ca78EGeP+dOyBfSWAQmEUF4iYgQ/SJJVanGKiMnuZmJTRi6MXr6aQiFfH5QRSn79cjtEcwg66QnRbo32ehVlF858PxUkjLIbo0EWtjyiWyjUd87H3aRpVDbJobAYcLa"
    encrypted_private_key = "g9elg0A8IPsnLl0Woez0OP8dd/cr1NRqvOmgCTpt+IlRmMEe3sUl077EPAKBwrFSQsdGDmRtNDvIu/7xZakrMcDRP1Q4SS8aYDCcV+zP28ufPAEV0sXR1ZL0VF63h1/p"
    
    print("🚀 شروع عملیات رمزگشایی کیف پول")
    print(f"🎯 آدرس هدف: {target_address}")
    print("-" * 60)
    
    print(f"📝 Address ID: 11744")
    print(f"🔗 Wallet ID: acfbe766-0f0a-4a9f-9010-6c2eaf547f61")
    print(f"⛓️ Blockchain ID: 2")
    print(f"🔒 عبارت رمزنگاری شده یافت شد")
    print(f"📏 طول داده رمزنگاری شده: {len(encrypted_phrase_key)} کاراکتر")
    
    # رمزگشایی عبارت ۱۲ کلمه‌ای
    try:
        decrypted_phrase = decrypt_mnemonic_aes(encrypted_phrase_key)
        
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
        
        # رمزگشایی کلید خصوصی
        try:
            decrypted_private_key = decrypt_private_key_aes(encrypted_private_key)
            print(f"\n🔑 کلید خصوصی رمزگشایی شده:")
            print(f"🔓 {decrypted_private_key}")
        except Exception as e:
            print(f"❌ خطا در رمزگشایی کلید خصوصی: {str(e)}")
        
        print("\n✅ عملیات با موفقیت انجام شد!")
        return decrypted_phrase
        
    except Exception as e:
        print(f"❌ خطا در رمزگشایی: {str(e)}")
        return None

if __name__ == "__main__":
    main() 