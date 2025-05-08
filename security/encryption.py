import os
import base64
from Crypto.Cipher import AES
import re

# کلید را از متغیرهای محیطی می‌خوانیم
AES_SECRET_KEY = os.environ.get('AES_SECRET_KEY', 'MySecretKey@1234')

def encrypt_private_key_aes(private_key: str) -> str:
    """رمزنگاری کلید خصوصی با AES-GCM"""
    secret_key_bytes = AES_SECRET_KEY.encode()
    cipher = AES.new(secret_key_bytes, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(private_key.encode())
    total_data = cipher.nonce + tag + ciphertext
    return base64.b64encode(total_data).decode()

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

def encrypt_mnemonic_aes(mnemonic: str) -> str:
    """رمزنگاری عبارت بازیابی با AES-GCM"""
    salt = os.urandom(16)
    secret_key_bytes = AES_SECRET_KEY.encode('utf-8')
    cipher = AES.new(secret_key_bytes, AES.MODE_GCM)
    plaintext = salt + mnemonic.encode('utf-8')
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    encrypted_data = salt + cipher.nonce + tag + ciphertext
    return base64.b64encode(encrypted_data).decode('utf-8')

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

def mask_private_key(text):
    """
    مخفی کردن کلید خصوصی در متن لاگ یا هر متن دیگر
    با استفاده از regex برای تشخیص الگوهای کلید خصوصی
    """
    # الگوهای مختلف کلید خصوصی
    patterns = [
        # Ethereum/BSC/Polygon/etc style (64 hex chars)
        r'(0x)?([0-9a-fA-F]{64})',
        
        # Shorter private keys with length > 30
        r'([0-9a-fA-F]{30,60})',
        
        # Bitcoin WIF format
        r'([5KL][1-9A-HJ-NP-Za-km-z]{50,52})',
        
        # Phrase "private_key" followed by anything except whitespace
        r'private_key\s*=\s*["\']?([^"\'\s]+)["\']?',
        
        # XRP format (Family Seed format starting with 's')
        r'(s[1-9A-HJ-NP-Za-km-z]{20,35})'
    ]
    
    # اگر متن وجود نداشته باشد یا رشته نباشد
    if not text or not isinstance(text, str):
        return text
        
    result = text
    for pattern in patterns:
        # جایگزینی با ***
        result = re.sub(pattern, lambda m: m.group(0)[0:4] + '***' + m.group(0)[-4:] if len(m.group(0)) > 8 else '***', result)
        
    return result 