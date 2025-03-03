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