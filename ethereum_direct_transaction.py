#!/usr/bin/env python3
"""
سیستم تراکنش مستقیم اتریوم (بدون Tatum)
Direct Ethereum transaction system (without Tatum)
"""

from web3 import Web3
from decimal import Decimal
import requests
import json
from datetime import datetime
import time

class DirectEthereumTransactionService:
    """سرویس تراکنش مستقیم اتریوم"""
    
    def __init__(self):
        # اتصال به چندین RPC endpoint
        self.rpc_endpoints = [
            "https://eth.llamarpc.com",
            "https://ethereum.publicnode.com", 
            "https://rpc.ankr.com/eth",
            "https://eth-mainnet.public.blastapi.io",
            "https://ethereum-rpc.publicnode.com"
        ]
        
        self.w3 = None
        self.current_rpc_index = 0
        
        # تلاش برای اتصال به RPC
        self.connect_to_rpc()

    def connect_to_rpc(self):
        """اتصال به بهترین RPC endpoint"""
        
        for i, rpc_url in enumerate(self.rpc_endpoints):
            try:
                print(f"🔗 تلاش اتصال به RPC {i+1}: {rpc_url}")
                
                w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 10}))
                
                # تست اتصال
                if w3.is_connected():
                    latest_block = w3.eth.get_block('latest')
                    if latest_block:
                        self.w3 = w3
                        self.current_rpc_index = i
                        print(f"✅ اتصال موفق به RPC {i+1}")
                        print(f"📦 آخرین بلاک: {latest_block['number']:,}")
                        return True
                        
            except Exception as e:
                print(f"❌ RPC {i+1} ناموفق: {str(e)}")
                continue
        
        print(f"❌ هیچ RPC endpoint کار نمی‌کند")
        return False

    def get_gas_price(self):
        """دریافت gas price بهینه"""
        
        try:
            # روش 1: از شبکه اتریوم
            network_gas_price = self.w3.eth.gas_price
            network_gas_price_gwei = network_gas_price / 10**9
            
            print(f"⛽ Gas price شبکه: {network_gas_price_gwei:.2f} Gwei")
            
            # روش 2: از Gas Station API
            try:
                response = requests.get("https://ethgasstation.info/api/ethgasAPI.json", timeout=5)
                if response.status_code == 200:
                    gas_data = response.json()
                    recommended_gas = gas_data.get('average', 20) / 10  # تبدیل به Gwei
                    
                    print(f"⛽ Gas price توصیه شده: {recommended_gas:.2f} Gwei")
                    
                    # انتخاب میانگین
                    final_gas_price = int((network_gas_price_gwei + recommended_gas) / 2 * 10**9)
                    return final_gas_price
                    
            except Exception as e:
                print(f"⚠️ خطا در Gas Station API: {str(e)}")
            
            # استفاده از gas price شبکه با ضریب ایمنی
            return int(network_gas_price * 1.1)  # 10% بیشتر برای اطمینان
            
        except Exception as e:
            print(f"❌ خطا در دریافت gas price: {str(e)}")
            # gas price پیش‌فرض (20 Gwei)
            return 20 * 10**9

    def validate_transaction(self, sender, recipient, amount, private_key):
        """اعتبارسنجی کامل تراکنش"""
        
        errors = []
        
        # بررسی آدرس‌ها
        if not self.w3.is_address(sender):
            errors.append("آدرس فرستنده نامعتبر")
        
        if not self.w3.is_address(recipient):
            errors.append("آدرس گیرنده نامعتبر")
        
        if sender.lower() == recipient.lower():
            errors.append("آدرس فرستنده و گیرنده نباید یکسان باشند")
        
        # بررسی مقدار
        try:
            amount_decimal = Decimal(str(amount))
            if amount_decimal <= 0:
                errors.append("مقدار باید بزرگتر از صفر باشد")
        except:
            errors.append("فرمت مقدار نامعتبر")
        
        # بررسی کلید خصوصی
        try:
            account = self.w3.eth.account.from_key(private_key)
            if account.address.lower() != sender.lower():
                errors.append("کلید خصوصی با آدرس فرستنده مطابقت ندارد")
        except:
            errors.append("کلید خصوصی نامعتبر")
        
        # بررسی موجودی
        try:
            balance = self.w3.eth.get_balance(sender)
            balance_eth = Decimal(balance) / Decimal(10**18)
            
            # برآورد کارمزد
            gas_price = self.get_gas_price()
            gas_limit = 21000
            fee_wei = gas_price * gas_limit
            fee_eth = Decimal(fee_wei) / Decimal(10**18)
            
            total_required = amount_decimal + fee_eth
            
            if balance_eth < total_required:
                errors.append(f"موجودی ناکافی. موجود: {balance_eth:.6f} ETH، مورد نیاز: {total_required:.6f} ETH")
                
        except Exception as e:
            errors.append(f"خطا در بررسی موجودی: {str(e)}")
        
        return errors

    def send_transaction_direct(self, sender, recipient, amount, private_key):
        """ارسال مستقیم تراکنش بدون Tatum"""
        
        print(f"🚀 شروع ارسال مستقیم تراکنش اتریوم")
        print(f"   از: {sender}")
        print(f"   به: {recipient}")
        print(f"   مقدار: {amount} ETH")
        
        try:
            # اعتبارسنجی
            validation_errors = self.validate_transaction(sender, recipient, amount, private_key)
            if validation_errors:
                error_msg = "; ".join(validation_errors)
                print(f"❌ خطای اعتبارسنجی: {error_msg}")
                return None, error_msg
            
            # تبدیل مقدار
            amount_decimal = Decimal(str(amount))
            amount_wei = self.w3.to_wei(amount_decimal, 'ether')
            
            # دریافت nonce
            nonce = self.w3.eth.get_transaction_count(sender)
            print(f"📝 Nonce: {nonce}")
            
            # دریافت gas price
            gas_price = self.get_gas_price()
            gas_price_gwei = gas_price / 10**9
            print(f"⛽ Gas Price: {gas_price_gwei:.2f} Gwei")
            
            # آماده‌سازی تراکنش
            transaction = {
                'from': sender,
                'to': recipient,
                'value': amount_wei,
                'gas': 21000,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': 1  # Ethereum mainnet
            }
            
            print(f"📋 پارامترهای تراکنش:")
            print(f"   Value: {amount_wei} Wei ({amount} ETH)")
            print(f"   Gas Limit: 21000")
            print(f"   Gas Price: {gas_price} Wei ({gas_price_gwei:.2f} Gwei)")
            print(f"   Chain ID: 1")
            
            # امضای تراکنش
            print(f"✍️ امضای تراکنش...")
            signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key)
            
            # ارسال تراکنش
            print(f"📤 ارسال تراکنش...")
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_hash_hex = tx_hash.hex()
            
            print(f"✅ تراکنش ارسال شد!")
            print(f"🔗 Transaction Hash: {tx_hash_hex}")
            print(f"🌐 Etherscan: https://etherscan.io/tx/{tx_hash_hex}")
            
            # انتظار برای تأیید
            print(f"⏳ انتظار برای تأیید...")
            
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
                
                if receipt['status'] == 1:
                    print(f"✅ تراکنش تأیید شد!")
                    print(f"📦 Block Number: {receipt['blockNumber']}")
                    print(f"⛽ Gas Used: {receipt['gasUsed']}")
                    
                    return {
                        'tx_hash': tx_hash_hex,
                        'status': 'confirmed',
                        'block_number': receipt['blockNumber'],
                        'gas_used': receipt['gasUsed'],
                        'method': 'direct_web3'
                    }, None
                else:
                    print(f"❌ تراکنش شکست خورد")
                    return None, "Transaction failed on blockchain"
                    
            except Exception as e:
                print(f"⚠️ خطا در انتظار تأیید: {str(e)}")
                # تراکنش ارسال شده ولی تأیید منتظر است
                return {
                    'tx_hash': tx_hash_hex,
                    'status': 'pending',
                    'method': 'direct_web3'
                }, None
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ خطا در ارسال: {error_msg}")
            
            # تشخیص نوع خطا
            if "insufficient funds" in error_msg.lower():
                return None, "موجودی ناکافی برای انجام تراکنش"
            elif "nonce too low" in error_msg.lower():
                return None, "خطا در ترتیب تراکنش. لطفاً چند ثانیه صبر کنید"
            elif "gas price too low" in error_msg.lower():
                return None, "کارمزد شبکه کم است. دوباره تلاش کنید"
            elif "network" in error_msg.lower():
                return None, "مشکل در اتصال به شبکه. دوباره تلاش کنید"
            else:
                return None, f"خطا در ارسال تراکنش: {error_msg}"

def test_direct_transaction():
    """تست تراکنش مستقیم"""
    
    print("="*60)
    print("🧪 تست تراکنش مستقیم اتریوم")
    print("="*60)
    
    # ایجاد سرویس
    service = DirectEthereumTransactionService()
    
    if not service.w3:
        print("❌ نتوانستم به شبکه اتریوم متصل شوم")
        return
    
    # پارامترهای تست (فقط برای نمایش - استفاده نکنید!)
    test_params = {
        'sender': '0x742d35Cc6634C0532925a3b8D52e9e8d6C0e94Cb',  # آدرس نمونه
        'recipient': '0x8ba1f109551bD432803012645Hac136c4c0e93Cb',  # آدرس نمونه
        'amount': '0.001',  # مقدار کم برای تست
        'private_key': 'your_private_key_here'  # کلید شما
    }
    
    print(f"⚠️ این فقط نمایش پارامترها است")
    print(f"📋 پارامترهای تست:")
    print(f"   From: {test_params['sender']}")
    print(f"   To: {test_params['recipient']}")
    print(f"   Amount: {test_params['amount']} ETH")
    
    print(f"\n💡 برای تست واقعی:")
    print("1. آدرس‌ها و کلید خصوصی واقعی وارد کنید")
    print("2. مقدار کم (مثل 0.001 ETH) استفاده کنید")
    print("3. ابتدا در testnet تست کنید")

def create_ethereum_service_patch():
    """ایجاد patch برای سرویس اتریوم"""
    
    patch_code = '''
    def send_transaction_direct_fallback(self, transaction_id: str, private_key: str):
        """
        روش پشتیبان: ارسال مستقیم بدون Tatum
        Fallback method: Direct sending without Tatum
        """
        try:
            # Get transaction data
            tx_data = self._get_transaction(transaction_id)
            if not tx_data:
                return {}, f"Transaction {transaction_id} not found"
            
            sender = tx_data['details']['sender']
            recipient = tx_data['details']['recipient']
            amount_str = tx_data['details']['amount']
            amount = Decimal(amount_str)
            
            self.logger.info(f"🔄 Method 4: Direct Web3 without Tatum")
            
            # اتصال مستقیم به چندین RPC
            rpc_endpoints = [
                "https://eth.llamarpc.com",
                "https://ethereum.publicnode.com",
                "https://rpc.ankr.com/eth"
            ]
            
            for rpc_url in rpc_endpoints:
                try:
                    # ایجاد اتصال جدید
                    direct_w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 15}))
                    
                    if not direct_w3.is_connected():
                        continue
                    
                    # دریافت اطلاعات شبکه
                    nonce = direct_w3.eth.get_transaction_count(sender)
                    gas_price = direct_w3.eth.gas_price
                    
                    # کاهش gas price اگر خیلی زیاد باشد
                    max_gas_price = 50 * 10**9  # 50 Gwei
                    if gas_price > max_gas_price:
                        gas_price = max_gas_price
                        self.logger.warning(f"Gas price reduced to {gas_price/10**9:.2f} Gwei")
                    
                    # آماده‌سازی تراکنش
                    transaction = {
                        'from': sender,
                        'to': recipient,
                        'value': direct_w3.to_wei(amount, 'ether'),
                        'gas': 21000,
                        'gasPrice': gas_price,
                        'nonce': nonce,
                        'chainId': 1
                    }
                    
                    # امضا
                    signed_txn = direct_w3.eth.account.sign_transaction(transaction, private_key)
                    
                    # ارسال
                    tx_hash = direct_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    tx_hash_hex = tx_hash.hex()
                    
                    self.logger.info(f"✅ SUCCESS: Direct Web3 transaction sent: {tx_hash_hex}")
                    
                    # Update transaction data
                    tx_data.update({
                        'tx_hash': tx_hash_hex,
                        'status': 'sent',
                        'sent_at': datetime.now().isoformat(),
                        'sent_via': 'direct_web3_fallback',
                        'method_used': 4,
                        'rpc_used': rpc_url
                    })
                    self._store_transaction(transaction_id, tx_data)
                    
                    return {
                        'transaction_id': transaction_id,
                        'tx_hash': tx_hash_hex,
                        'status': 'sent',
                        'method': 'direct_web3_fallback'
                    }, None
                    
                except Exception as rpc_error:
                    self.logger.warning(f"RPC {rpc_url} failed: {str(rpc_error)}")
                    continue
            
            return {}, "All direct RPC methods failed"
            
        except Exception as e:
            self.logger.error(f"Direct fallback method failed: {str(e)}")
            return {}, str(e)
    '''
    
    return patch_code

def main():
    print("🔧 راه‌حل خطای HTTP 400 اتریوم")
    print("="*50)
    
    print("❌ مشکل فعلی:")
    print("   HTTP 400: Bad syntax or cannot be fulfilled")
    print("   Error estimating network fee")
    print("   تراکنش اتریوم ناموفق")
    
    print(f"\n🔍 علت احتمالی:")
    print("   1. مشکل در Tatum API")
    print("   2. پارامترهای نامعتبر در درخواست")
    print("   3. شلوغی شبکه اتریوم")
    print("   4. Gas price بالا یا نامعتبر")
    
    # ایجاد سرویس تست
    print(f"\n🧪 تست اتصال مستقیم...")
    test_direct_transaction()
    
    # ایجاد patch
    patch = create_ethereum_service_patch()
    
    with open('ethereum_direct_patch.py', 'w', encoding='utf-8') as f:
        f.write(f'''#!/usr/bin/env python3
# Patch برای اضافه کردن روش مستقیم به ethereum_service.py

{patch}
''')
    
    print(f"\n💾 Patch در فایل ethereum_direct_patch.py ذخیره شد")
    
    print(f"\n🔄 مراحل اعمال:")
    print("1. کد patch را به ethereum_service.py اضافه کنید")
    print("2. در انتهای متد send_transaction، قبل از return error نهایی:")
    print("   result, error = self.send_transaction_direct_fallback(transaction_id, private_key)")
    print("   if not error: return result, error")
    print("3. تست با تراکنش واقعی")
    
    print(f"\n🎯 مزایای روش مستقیم:")
    print("   ✅ بدون وابستگی به Tatum")
    print("   ✅ کنترل کامل پارامترها")
    print("   ✅ اتصال مستقیم به شبکه")
    print("   ✅ چندین RPC endpoint")

if __name__ == "__main__":
    main()
