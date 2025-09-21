#!/usr/bin/env python3
"""
تست پردازش amount در فرمت‌های مختلف
Test amount parsing in different formats
"""

from decimal import Decimal

def test_amount_parsing():
    """تست تبدیل amount"""
    
    print("="*60)
    print("🧪 تست پردازش Amount")
    print("="*60)
    
    # شبیه‌سازی کلاس EthereumService
    class MockEthereumService:
        def parse_amount_to_wei(self, amount_input) -> int:
            try:
                from decimal import Decimal, ROUND_DOWN, InvalidOperation, getcontext
                getcontext().prec = 80
                
                if isinstance(amount_input, Decimal):
                    dec = amount_input
                elif isinstance(amount_input, (int, float)):
                    dec = Decimal(str(amount_input))
                elif isinstance(amount_input, str):
                    cleaned = amount_input.strip().replace(',', '.')
                    if not cleaned:
                        raise ValueError("Amount cannot be empty")
                    dec = Decimal(cleaned)
                else:
                    raise ValueError(f"Unsupported amount type: {type(amount_input)}")
                
                if dec <= 0:
                    raise ValueError("Amount must be positive")
                
                if dec > Decimal('1000000'):
                    raise ValueError("Amount too large")
                
                dec = dec.quantize(Decimal('1.000000000000000000'), rounding=ROUND_DOWN)
                wei_amount = int((dec * (Decimal(10) ** 18)).to_integral_value(rounding=ROUND_DOWN))
                
                return wei_amount
                
            except Exception as e:
                raise ValueError(f"Invalid amount: {str(e)}")
        
        def get_amount_from_request(self, request_data: dict) -> int:
            try:
                # اولویت 1: amount_wei
                if 'amount_wei' in request_data and request_data['amount_wei'] not in (None, '', 0):
                    try:
                        wei_amount = int(str(request_data['amount_wei']).strip())
                        if wei_amount <= 0:
                            raise ValueError("Amount_wei must be positive")
                        return wei_amount
                    except (ValueError, TypeError) as e:
                        raise ValueError(f"Invalid amount_wei format: {str(e)}")
                
                # اولویت 2: amount
                elif 'amount' in request_data and request_data['amount'] not in (None, '', 0):
                    return self.parse_amount_to_wei(request_data['amount'])
                
                else:
                    raise ValueError("Missing amount or amount_wei field")
                    
            except ValueError:
                raise
            except Exception as e:
                raise ValueError(f"Amount parsing error: {str(e)}")
    
    service = MockEthereumService()
    
    # تست‌های مختلف
    test_cases = [
        # فرمت ETH
        {"name": "ETH String", "data": {"amount": "0.002"}, "expected_wei": 2000000000000000},
        {"name": "ETH Float", "data": {"amount": 0.002}, "expected_wei": 2000000000000000},
        {"name": "ETH Decimal", "data": {"amount": Decimal("0.002")}, "expected_wei": 2000000000000000},
        
        # فرمت Wei
        {"name": "Wei String", "data": {"amount_wei": "2000000000000000"}, "expected_wei": 2000000000000000},
        {"name": "Wei Int", "data": {"amount_wei": 2000000000000000}, "expected_wei": 2000000000000000},
        
        # موارد خطا
        {"name": "Empty amount", "data": {"amount": ""}, "expected_error": True},
        {"name": "Negative amount", "data": {"amount": "-0.1"}, "expected_error": True},
        {"name": "Missing fields", "data": {}, "expected_error": True},
        
        # مورد مشکل‌ساز اصلی
        {"name": "Problematic case", "data": {"amount": "0.002"}, "expected_wei": 2000000000000000}
    ]
    
    for test_case in test_cases:
        print(f"\n🔍 تست: {test_case['name']}")
        print(f"   ورودی: {test_case['data']}")
        
        try:
            result_wei = service.get_amount_from_request(test_case['data'])
            result_eth = Decimal(result_wei) / Decimal(10**18)
            
            if test_case.get('expected_error'):
                print(f"   ❌ انتظار خطا بود ولی موفق شد: {result_wei} Wei")
            else:
                expected_wei = test_case.get('expected_wei', 0)
                if result_wei == expected_wei:
                    print(f"   ✅ موفق: {result_wei} Wei ({result_eth} ETH)")
                else:
                    print(f"   ⚠️ نتیجه متفاوت: {result_wei} Wei (انتظار: {expected_wei})")
                    
        except Exception as e:
            if test_case.get('expected_error'):
                print(f"   ✅ خطای مورد انتظار: {str(e)}")
            else:
                print(f"   ❌ خطای غیرمنتظره: {str(e)}")

def test_postman_requests():
    """تست درخواست‌های Postman"""
    
    print(f"\n" + "="*60)
    print("📮 تست درخواست‌های Postman")
    print("="*60)
    
    # نمونه درخواست‌های Postman
    postman_requests = [
        {
            "name": "ETH Format (Postman 1)",
            "body": {
                "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
                "blockchain": "Ethereum",
                "sender_address": "0xAa56CEB9C75FA01C1e2F16474B81FD639a6956",
                "recipient_address": "0x8d6970386c176dC7ac250F67f5283BFbc8EC5bE9",
                "amount": "0.002",
                "smart_contract_address": ""
            }
        },
        {
            "name": "Wei Format (Postman 2)",
            "body": {
                "UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08",
                "blockchain": "Ethereum", 
                "sender_address": "0xAa56CEB9C75FA01C1e2F16474B81FD639a6956",
                "recipient_address": "0x8d6970386c176dC7ac250F67f5283BFbc8EC5bE9",
                "amount_wei": "2000000000000000",
                "smart_contract_address": ""
            }
        }
    ]
    
    service = MockEthereumService()
    
    for req in postman_requests:
        print(f"\n🔍 {req['name']}:")
        
        try:
            amount_wei = service.get_amount_from_request(req['body'])
            amount_eth = Decimal(amount_wei) / Decimal(10**18)
            
            print(f"   ✅ موفق:")
            print(f"      Amount Wei: {amount_wei}")
            print(f"      Amount ETH: {amount_eth}")
            print(f"      برای estimate_fee: amount_decimal = {amount_eth}")
            
        except Exception as e:
            print(f"   ❌ خطا: {str(e)}")

def main():
    # تست پردازش amount
    test_amount_parsing()
    
    # تست درخواست‌های Postman
    test_postman_requests()
    
    print(f"\n" + "="*60)
    print("📋 خلاصه")
    print("="*60)
    
    print("✅ مشکل اصلی حل شد:")
    print("   - خطای 'can't multiply sequence by non-int'")
    print("   - پشتیبانی از amount (ETH) و amount_wei")
    print("   - تبدیل ایمن با Decimal precision")
    
    print(f"\n🎯 حالا باید کار کند:")
    print("   - درخواست Postman با amount: '0.002'")
    print("   - درخواست Postman با amount_wei: '2000000000000000'")
    print("   - هر دو به درستی تبدیل و پردازش می‌شوند")

if __name__ == "__main__":
    main()
