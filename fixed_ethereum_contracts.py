#!/usr/bin/env python3
"""
Fixed Ethereum Smart Contracts Finder
جستجوگر اصلاح شده قراردادهای هوشمند اتریوم
"""

import requests
import json
from datetime import datetime, timedelta
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class FixedEthereumContractsFinder:
    def __init__(self):
        self.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY', '77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY')
        self.base_url = "https://api.etherscan.io/api"
        
        # محاسبه صحیح تاریخ (سال 2024 نه 2025!)
        now = datetime.now()
        self.start_date = datetime(now.year, now.month, 1)
        self.end_date = now
        self.start_timestamp = int(self.start_date.timestamp())
        self.end_timestamp = int(self.end_date.timestamp())
        
        print(f"📅 بازه جستجو: {self.start_date.strftime('%Y-%m-%d')} تا {self.end_date.strftime('%Y-%m-%d')}")
        print(f"🕐 Timestamp: {self.start_timestamp} تا {self.end_timestamp}")
        
        # تایید تاریخ
        print(f"✅ تایید: {datetime.fromtimestamp(self.start_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")

    def get_latest_block_number(self):
        """دریافت شماره آخرین بلاک"""
        try:
            url = f"{self.base_url}?module=proxy&action=eth_blockNumber&apikey={self.etherscan_api_key}"
            response = requests.get(url)
            data = response.json()
            
            if data.get('result'):
                latest_block = int(data['result'], 16)
                return latest_block
            return None
        except Exception as e:
            print(f"❌ خطا در دریافت آخرین بلاک: {str(e)}")
            return None

    def get_block_by_timestamp(self, timestamp, closest='before'):
        """دریافت شماره بلاک بر اساس timestamp"""
        try:
            url = f"{self.base_url}?module=block&action=getblocknobytime&timestamp={timestamp}&closest={closest}&apikey={self.etherscan_api_key}"
            response = requests.get(url)
            data = response.json()
            
            if data.get('result'):
                return int(data['result'])
            return None
        except Exception as e:
            print(f"❌ خطا در دریافت بلاک: {str(e)}")
            return None

    def search_contracts_by_creation_method(self):
        """جستجوی قراردادها با روش بررسی تراکنش‌های ایجاد"""
        try:
            latest_block = self.get_latest_block_number()
            if not latest_block:
                return []
            
            print(f"📦 آخرین بلاک: {latest_block}")
            
            # محاسبه بلاک شروع بر اساس تاریخ
            start_block = self.get_block_by_timestamp(self.start_timestamp)
            if not start_block:
                # اگر نتوانست پیدا کند، از 30 روز پیش شروع کن
                start_block = latest_block - (30 * 24 * 60 * 4)  # تقریباً 30 روز
            
            print(f"🔍 جستجو از بلاک {start_block} تا {latest_block}")
            
            contracts_found = []
            
            # جستجو در چند مرحله
            block_range = latest_block - start_block
            chunk_size = min(block_range // 20, 50000)  # تقسیم به قطعات کوچکتر
            
            for i in range(20):
                chunk_start = start_block + (i * chunk_size)
                chunk_end = min(chunk_start + chunk_size, latest_block)
                
                if chunk_start >= latest_block:
                    break
                
                print(f"📊 بررسی بلاک‌های {chunk_start} تا {chunk_end}")
                
                # جستجوی تراکنش‌های ایجاد قرارداد
                found_in_chunk = self.find_contracts_in_range(chunk_start, chunk_end)
                contracts_found.extend(found_in_chunk)
                
                if len(contracts_found) >= 50:  # محدود کردن نتایج
                    print(f"✅ تعداد کافی قرارداد یافت شد: {len(contracts_found)}")
                    break
                
                time.sleep(0.3)  # Rate limiting
            
            return contracts_found
            
        except Exception as e:
            print(f"❌ خطا در جستجو: {str(e)}")
            return []

    def find_contracts_in_range(self, start_block, end_block):
        """جستجوی قراردادها در یک بازه بلاک"""
        try:
            contracts = []
            
            # جستجوی تراکنش‌ها
            for page in range(1, 4):  # 3 صفحه برای هر بازه
                url = f"{self.base_url}?module=account&action=txlist&startblock={start_block}&endblock={end_block}&page={page}&offset=100&sort=desc&apikey={self.etherscan_api_key}"
                
                response = requests.get(url)
                data = response.json()
                
                if data.get('status') == '1' and data.get('result'):
                    transactions = data['result']
                    
                    for tx in transactions:
                        # بررسی تراکنش ایجاد قرارداد
                        if (tx.get('to') == '' or tx.get('to') is None) and tx.get('input') != '0x':
                            tx_timestamp = int(tx.get('timeStamp', 0))
                            
                            # بررسی بازه زمانی
                            if tx_timestamp >= self.start_timestamp:
                                contract_address = self.get_contract_address_from_tx(tx['hash'])
                                
                                if contract_address:
                                    contract_info = {
                                        'address': contract_address,
                                        'creator': tx['from'],
                                        'tx_hash': tx['hash'],
                                        'block_number': int(tx['blockNumber']),
                                        'timestamp': tx_timestamp,
                                        'date': datetime.fromtimestamp(tx_timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                                        'gas_used': int(tx.get('gasUsed', 0)),
                                        'value': tx.get('value', '0')
                                    }
                                    
                                    contracts.append(contract_info)
                                    print(f"✅ قرارداد جدید: {contract_address} ({contract_info['date']})")
                
                time.sleep(0.2)
            
            return contracts
            
        except Exception as e:
            print(f"❌ خطا در جستجوی بازه: {str(e)}")
            return []

    def get_contract_address_from_tx(self, tx_hash):
        """دریافت آدرس قرارداد از transaction receipt"""
        try:
            url = f"{self.base_url}?module=proxy&action=eth_getTransactionReceipt&txhash={tx_hash}&apikey={self.etherscan_api_key}"
            response = requests.get(url)
            data = response.json()
            
            if data.get('result') and data['result'].get('contractAddress'):
                return data['result']['contractAddress']
            
            return None
        except Exception as e:
            return None

    def search_recent_contracts_alternative(self):
        """روش جایگزین: جستجوی قراردادهای اخیر"""
        try:
            print("🔄 استفاده از روش جایگزین...")
            
            latest_block = self.get_latest_block_number()
            contracts_found = []
            
            # جستجوی در بلاک‌های اخیر با دقت بیشتر
            blocks_to_check = 50000  # 7-10 روز اخیر
            start_block = latest_block - blocks_to_check
            
            print(f"🔍 بررسی {blocks_to_check} بلاک اخیر...")
            
            # استفاده از Etherscan's contract creation API اگر موجود باشد
            for page in range(1, 10):
                print(f"📄 صفحه {page}...")
                
                # جستجوی عمومی تراکنش‌ها
                url = f"{self.base_url}?module=account&action=txlist&startblock={start_block}&endblock=latest&page={page}&offset=100&sort=desc&apikey={self.etherscan_api_key}"
                
                response = requests.get(url)
                data = response.json()
                
                if data.get('status') == '1' and data.get('result'):
                    transactions = data['result']
                    
                    contract_count = 0
                    for tx in transactions:
                        if tx.get('to') == '':  # Contract creation
                            tx_timestamp = int(tx.get('timeStamp', 0))
                            
                            # فقط قراردادهای این ماه
                            if tx_timestamp >= self.start_timestamp:
                                contract_address = self.get_contract_address_from_tx(tx['hash'])
                                
                                if contract_address:
                                    contract_info = {
                                        'address': contract_address,
                                        'creator': tx['from'],
                                        'tx_hash': tx['hash'],
                                        'block_number': int(tx['blockNumber']),
                                        'timestamp': tx_timestamp,
                                        'date': datetime.fromtimestamp(tx_timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                                        'gas_used': int(tx.get('gasUsed', 0))
                                    }
                                    
                                    contracts_found.append(contract_info)
                                    contract_count += 1
                                    print(f"✅ {contract_address} - {contract_info['date']}")
                    
                    if contract_count == 0:
                        print(f"⚠️ هیچ قراردادی در صفحه {page} یافت نشد")
                
                time.sleep(0.3)
                
                if len(contracts_found) >= 20:
                    break
            
            return contracts_found
            
        except Exception as e:
            print(f"❌ خطا در روش جایگزین: {str(e)}")
            return []

    def get_verified_contracts_list(self):
        """دریافت لیست قراردادهای تایید شده اخیر"""
        try:
            print("📋 دریافت قراردادهای تایید شده...")
            
            # این API ممکن است محدود باشد
            url = f"{self.base_url}?module=contract&action=getcontractcreation&contractaddresses=&apikey={self.etherscan_api_key}"
            
            response = requests.get(url)
            data = response.json()
            
            print(f"📊 پاسخ API: {data}")
            
        except Exception as e:
            print(f"❌ خطا در دریافت قراردادهای تایید شده: {str(e)}")

    def save_results(self, contracts):
        """ذخیره نتایج"""
        if not contracts:
            print("😔 هیچ قراردادی برای ذخیره یافت نشد")
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"ethereum_contracts_{timestamp}.json"
        
        result_data = {
            'search_info': {
                'start_date': self.start_date.isoformat(),
                'end_date': self.end_date.isoformat(),
                'start_timestamp': self.start_timestamp,
                'end_timestamp': self.end_timestamp,
                'total_found': len(contracts)
            },
            'contracts': contracts
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 {len(contracts)} قرارداد در فایل {filename} ذخیره شد")
        
        # نمایش آدرس‌ها
        print(f"\n📋 آدرس قراردادهای یافت شده:")
        for i, contract in enumerate(contracts, 1):
            print(f"{i:2d}. {contract['address']} - {contract['date']}")

    def run(self):
        """اجرای اصلی"""
        print("🚀 شروع جستجوی اصلاح شده...")
        
        # روش 1: جستجوی بر اساس بلاک
        contracts = self.search_contracts_by_creation_method()
        
        if not contracts:
            print("🔄 تلاش با روش جایگزین...")
            contracts = self.search_recent_contracts_alternative()
        
        if not contracts:
            print("🔍 تلاش برای دریافت قراردادهای تایید شده...")
            self.get_verified_contracts_list()
            
            # جستجوی دستی در چند بلاک اخیر
            print("🔍 جستجوی دستی در بلاک‌های اخیر...")
            latest_block = self.get_latest_block_number()
            if latest_block:
                # بررسی 100 بلاک اخیر یکی یکی
                for i in range(100):
                    block_num = latest_block - i
                    print(f"🔍 بررسی بلاک {block_num}...")
                    
                    # دریافت تراکنش‌های بلاک
                    block_url = f"{self.base_url}?module=proxy&action=eth_getBlockByNumber&tag=0x{block_num:x}&boolean=true&apikey={self.etherscan_api_key}"
                    response = requests.get(block_url)
                    data = response.json()
                    
                    if data.get('result') and data['result'].get('transactions'):
                        transactions = data['result']['transactions']
                        
                        for tx in transactions:
                            if tx.get('to') is None:  # Contract creation
                                print(f"✅ قرارداد در بلاک {block_num}: {tx.get('hash')}")
                                # اینجا می‌توانید جزئیات بیشتر استخراج کنید
                    
                    time.sleep(0.1)
                    
                    if i >= 10:  # فقط 10 بلاک اول را بررسی کن
                        break
        
        # ذخیره نتایج
        if contracts:
            self.save_results(contracts)
        else:
            print("😔 متأسفانه هیچ قراردادی در بازه زمانی مشخص شده یافت نشد")
            print("💡 ممکن است:")
            print("   - بازه زمانی خیلی کوتاه باشد")
            print("   - API محدودیت داشته باشد") 
            print("   - نیاز به کلید API بهتر باشد")

def main():
    print("=" * 60)
    print("🔧 Fixed Ethereum Smart Contracts Finder")
    print("جستجوگر اصلاح شده قراردادهای هوشمند اتریوم")
    print("=" * 60)
    
    try:
        finder = FixedEthereumContractsFinder()
        finder.run()
        
    except KeyboardInterrupt:
        print("\n⏹️ عملیات متوقف شد")
    except Exception as e:
        print(f"❌ خطا: {str(e)}")
    
    print("\n" + "=" * 60)
    print("✅ پایان")

if __name__ == "__main__":
    main()
