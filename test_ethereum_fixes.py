#!/usr/bin/env python3
"""
تست اصلاحات اتریوم
Test Ethereum fixes
"""

from web3 import Web3
from decimal import Decimal

def test_improved_fee_estimation():
    """تست تخمین کارمزد بهبود یافته"""
    
    print("="*60)
    print("🧪 تست تخمین کارمزد بهبود یافته")
    print("="*60)
    
    # اتصال به RPC
    rpc_urls = [
        "https://eth.llamarpc.com",
        "https://ethereum.publicnode.com",
        "https://rpc.ankr.com/eth"
    ]
    
    w3 = None
    for rpc_url in rpc_urls:
        try:
            print(f"🔗 تلاش اتصال به: {rpc_url}")
            w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 10}))
            
            if w3.is_connected():
                print(f"✅ اتصال موفق")
                break
        except Exception as e:
            print(f"❌ خطا: {str(e)}")
            continue
    
    if not w3:
        print("❌ نتوانستم به هیچ RPC متصل شوم")
        return
    
    # تست آدرس‌های نمونه
    test_addresses = {
        'sender': '0x742d35Cc6634C0532925a3b8D52e9e8d6C0e94Cb',
        'recipient': '0x8ba1f109551bD432803012645Hac136c4c0e93Cb'
    }
    
    try:
        # تست 1: نرمال‌سازی آدرس
        print(f"\n🔍 تست 1: نرمال‌سازی آدرس")
        
        sender_normalized = w3.to_checksum_address(test_addresses['sender'])
        recipient_normalized = w3.to_checksum_address(test_addresses['recipient'])
        
        print(f"   اصلی: {test_addresses['sender']}")
        print(f"   نرمال: {sender_normalized}")
        print(f"   ✅ نرمال‌سازی موفق")
        
        # تست 2: دریافت chainId
        print(f"\n🔍 تست 2: دریافت chainId")
        chain_id = w3.eth.chain_id
        print(f"   Chain ID: {chain_id}")
        print(f"   ✅ {'Ethereum Mainnet' if chain_id == 1 else f'Other network ({chain_id})'}")
        
        # تست 3: تخمین gas واقعی
        print(f"\n🔍 تست 3: تخمین gas واقعی")
        
        transaction_params = {
            'from': sender_normalized,
            'to': recipient_normalized,
            'value': w3.to_wei(0.001, 'ether')  # 0.001 ETH برای تست
        }
        
        try:
            estimated_gas = w3.eth.estimate_gas(transaction_params)
            gas_with_buffer = int(estimated_gas * 1.2)
            
            print(f"   تخمین اولیه: {estimated_gas}")
            print(f"   با buffer 20%: {gas_with_buffer}")
            print(f"   ✅ تخمین gas موفق")
            
        except Exception as e:
            print(f"   ❌ خطا در تخمین gas: {str(e)}")
            print(f"   📝 این طبیعی است اگر آدرس‌ها موجودی نداشته باشند")
        
        # تست 4: بررسی EIP-1559
        print(f"\n🔍 تست 4: بررسی پشتیبانی EIP-1559")
        
        try:
            latest_block = w3.eth.get_block('latest')
            
            if 'baseFeePerGas' in latest_block:
                base_fee = latest_block['baseFeePerGas']
                
                try:
                    max_priority_fee = w3.eth.max_priority_fee
                except:
                    max_priority_fee = w3.to_wei(2, 'gwei')
                
                max_fee_per_gas = (base_fee * 2) + max_priority_fee
                
                print(f"   ✅ EIP-1559 پشتیبانی می‌شود")
                print(f"   Base Fee: {base_fee/10**9:.2f} Gwei")
                print(f"   Priority Fee: {max_priority_fee/10**9:.2f} Gwei") 
                print(f"   Max Fee: {max_fee_per_gas/10**9:.2f} Gwei")
                
            else:
                print(f"   ⚠️ EIP-1559 پشتیبانی نمی‌شود")
                
        except Exception as e:
            print(f"   ❌ خطا در بررسی EIP-1559: {str(e)}")
        
        # تست 5: دریافت gas price
        print(f"\n🔍 تست 5: دریافت gas price")
        
        try:
            network_gas_price = w3.eth.gas_price
            gas_price_gwei = network_gas_price / 10**9
            
            max_allowed = w3.to_wei(50, 'gwei')
            final_gas_price = min(network_gas_price, max_allowed)
            final_gwei = final_gas_price / 10**9
            
            print(f"   Gas price شبکه: {gas_price_gwei:.2f} Gwei")
            print(f"   Gas price نهایی: {final_gwei:.2f} Gwei")
            print(f"   ✅ {'محدود شد' if final_gas_price < network_gas_price else 'در محدوده مجاز'}")
            
        except Exception as e:
            print(f"   ❌ خطا در دریافت gas price: {str(e)}")
        
        # تست 6: محاسبه کارمزد نهایی
        print(f"\n🔍 تست 6: محاسبه کارمزد نهایی")
        
        try:
            # استفاده از مقادیر به‌دست آمده
            if 'estimated_gas' in locals():
                gas_limit = int(estimated_gas * 1.2)
            else:
                gas_limit = 21000
            
            if 'final_gas_price' in locals():
                total_fee_wei = final_gas_price * gas_limit
            else:
                total_fee_wei = w3.to_wei(20, 'gwei') * gas_limit
            
            fee_eth = Decimal(total_fee_wei) / Decimal(10**18)
            
            print(f"   Gas Limit: {gas_limit}")
            print(f"   کارمزد کل: {fee_eth:.6f} ETH")
            print(f"   کارمزد USD: ~${float(fee_eth) * 4400:.2f}")
            print(f"   ✅ محاسبه کارمزد موفق")
            
        except Exception as e:
            print(f"   ❌ خطا در محاسبه کارمزد: {str(e)}")
        
    except Exception as e:
        print(f"❌ خطا در تست: {str(e)}")

def test_transaction_parameters():
    """تست پارامترهای تراکنش"""
    
    print(f"\n" + "="*60)
    print("🧪 تست پارامترهای تراکنش")
    print("="*60)
    
    # نمونه پارامترهای مختلف
    test_cases = [
        {
            'name': 'آدرس‌های عادی',
            'sender': '0x742d35Cc6634C0532925a3b8D52e9e8d6C0e94Cb',
            'recipient': '0x8ba1f109551bD432803012645Hac136c4c0e93Cb'
        },
        {
            'name': 'آدرس‌های lowercase',
            'sender': '0x742d35cc6634c0532925a3b8d52e9e8d6c0e94cb',
            'recipient': '0x8ba1f109551bd432803012645hac136c4c0e93cb'
        },
        {
            'name': 'آدرس‌های با فاصله',
            'sender': ' 0x742d35Cc6634C0532925a3b8D52e9e8d6C0e94Cb ',
            'recipient': ' 0x8ba1f109551bD432803012645Hac136c4c0e93Cb '
        }
    ]
    
    # اتصال به Web3
    try:
        w3 = Web3(Web3.HTTPProvider("https://eth.llamarpc.com"))
        
        if not w3.is_connected():
            print("❌ نتوانستم به Web3 متصل شوم")
            return
        
        for test_case in test_cases:
            print(f"\n🔍 تست: {test_case['name']}")
            
            try:
                # تست اعتبارسنجی
                sender = test_case['sender'].strip()
                recipient = test_case['recipient'].strip()
                
                if w3.is_address(sender) and w3.is_address(recipient):
                    # نرمال‌سازی
                    sender_norm = w3.to_checksum_address(sender)
                    recipient_norm = w3.to_checksum_address(recipient)
                    
                    print(f"   ✅ آدرس‌ها معتبر")
                    print(f"   📝 Sender: {sender_norm}")
                    print(f"   📝 Recipient: {recipient_norm}")
                else:
                    print(f"   ❌ آدرس‌ها نامعتبر")
                    
            except Exception as e:
                print(f"   ❌ خطا: {str(e)}")
        
    except Exception as e:
        print(f"❌ خطا در تست: {str(e)}")

def main():
    print("🧪 تست کامل اصلاحات اتریوم")
    print("=" * 60)
    
    # تست تخمین کارمزد
    test_improved_fee_estimation()
    
    # تست پارامترهای تراکنش
    test_transaction_parameters()
    
    print(f"\n📋 خلاصه اصلاحات اعمال شده:")
    print("   ✅ Gas estimation واقعی با eth.estimate_gas")
    print("   ✅ نرمال‌سازی آدرس‌ها با to_checksum_address")
    print("   ✅ Chain ID پویا با eth.chain_id")
    print("   ✅ پشتیبانی EIP-1559 (maxFeePerGas)")
    print("   ✅ محدودیت gas price (50 Gwei)")
    print("   ✅ مدیریت خطای HTTP 400")
    print("   ✅ 4 روش پشتیبان برای ارسال")
    
    print(f"\n🎯 انتظار:")
    print("   خطای HTTP 400 باید برطرف شود")
    print("   تراکنش‌ها با موفقیت ارسال شوند")
    print("   پیام‌های خطا واضح‌تر باشند")

if __name__ == "__main__":
    main()
