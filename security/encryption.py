import os
import base64
from Crypto.Cipher import AES

# کلید را از متغیرهای محیطی می‌خوانیم
AES_SECRET_KEY = os.environ.get('AES_SECRET_KEY', 'MySecretKey@1234')

def encrypt_private_key_aes(private_key: str) -> str:
    """رمزنگاری کلید خصوصی با AES-GCM"""
    secret_key_bytes = AES_SECRET_KEY.encode()
    cipher = AES.new(secret_key_bytes, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(private_key.encode())
    total_data = cipher.nonce + tag + ciphertext
    return base64.b64encode(total_data).decode()

def encrypt_mnemonic_aes(mnemonic: str) -> str:
    """رمزنگاری عبارت بازیابی با AES-GCM"""
    salt = os.urandom(16)
    secret_key_bytes = AES_SECRET_KEY.encode('utf-8')
    cipher = AES.new(secret_key_bytes, AES.MODE_GCM)
    plaintext = salt + mnemonic.encode('utf-8')
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    encrypted_data = salt + cipher.nonce + tag + ciphertext
    return base64.b64encode(encrypted_data).decode('utf-8') 