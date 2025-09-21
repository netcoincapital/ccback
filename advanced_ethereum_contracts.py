#!/usr/bin/env python3
"""
Advanced Ethereum Smart Contracts Finder
جستجوگر پیشرفته قراردادهای هوشمند اتریوم با فیلترهای مختلف
"""

import requests
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AdvancedEthereumContractsFinder:
    def __init__(self):
        self.etherscan_api_key = os.getenv('ETHERSCAN_API_KEY', '77D1W3AMVN6ZGUXQ7116ECFQC2M9M3WFKY')
        self.base_url = "https://api.etherscan.io/api"
        
        # محاسبه بازه زمانی
        now = datetime.now()
        self.start_date = datetime(now.year, now.month, 1)
        self.end_date = now
        self.start_timestamp = int(self.start_date.timestamp())
        
        print(f"📅 بازه جستجو: {self.start_date.strftime('%Y-%m-%d')} تا {self.end_date.strftime('%Y-%m-%d')}")

    def get_contract_creation_events(self, start_block, end_block):
        """دریافت رویدادهای ایجاد قرارداد"""
        try:
            # جستجوی لاگ‌های ایجاد قرارداد
            url = f"{self.base_url}?module=logs&action=getLogs&fromBlock={start_block}&toBlock={end_block}&topic0=0x000000000000000000000000000000000000000000000000000000000000000&apikey={self.etherscan_api_key}"
            
            response = requests.get(url)
            data = response.json()
            
            return data.get('result', [])
            
        except Exception as e:
            print(f"❌ خطا در دریافت رویدادها: {str(e)}")
            return []

    def analyze_contract(self, address):
        """تحلیل دقیق قرارداد"""
        try:
            contract_info = {
                'address': address,
                'bytecode_size': 0,
                'is_verified': False,
                'contract_name': None,
                'compiler_version': None,
                'optimization': None,
                'source_code_lines': 0,
                'functions_count': 0,
                'events_count': 0,
                'is_proxy': False,
                'is_token': False,
                'token_standard': None
            }
            
            # دریافت bytecode
            code_url = f"{self.base_url}?module=proxy&action=eth_getCode&address={address}&tag=latest&apikey={self.etherscan_api_key}"
            code_response = requests.get(code_url)
            code_data = code_response.json()
            
            if code_data.get('result') and code_data['result'] != '0x':
                contract_info['bytecode_size'] = len(code_data['result']) // 2 - 1
                
                # بررسی الگوهای مختلف
                bytecode = code_data['result'].lower()
                
                # تشخیص proxy pattern
                if '363d3d373d3d3d363d73' in bytecode or 'delegatecall' in bytecode:
                    contract_info['is_proxy'] = True
                
                # تشخیص توکن (بررسی function signatures)
                token_signatures = [
                    '18160ddd',  # totalSupply()
                    '70a08231',  # balanceOf(address)
                    'a9059cbb',  # transfer(address,uint256)
                    '095ea7b3'   # approve(address,uint256)
                ]
                
                token_matches = sum(1 for sig in token_signatures if sig in bytecode)
                if token_matches >= 3:
                    contract_info['is_token'] = True
                    
                    # تشخیص استاندارد توکن
                    if 'a22cb465' in bytecode:  # setApprovalForAll
                        contract_info['token_standard'] = 'ERC721'
                    elif '4e1273f4' in bytecode:  # balanceOfBatch
                        contract_info['token_standard'] = 'ERC1155'
                    else:
                        contract_info['token_standard'] = 'ERC20'
            
            # دریافت source code
            source_url = f"{self.base_url}?module=contract&action=getsourcecode&address={address}&apikey={self.etherscan_api_key}"
            source_response = requests.get(source_url)
            source_data = source_response.json()
            
            if source_data.get('status') == '1' and source_data.get('result'):
                source_info = source_data['result'][0]
                
                if source_info.get('SourceCode'):
                    contract_info['is_verified'] = True
                    contract_info['contract_name'] = source_info.get('ContractName')
                    contract_info['compiler_version'] = source_info.get('CompilerVersion')
                    contract_info['optimization'] = source_info.get('OptimizationUsed') == '1'
                    
                    # تحلیل source code
                    source_code = source_info.get('SourceCode', '')
                    if source_code:
                        contract_info['source_code_lines'] = len(source_code.split('\n'))
                        contract_info['functions_count'] = source_code.count('function ')
                        contract_info['events_count'] = source_code.count('event ')
            
            return contract_info
            
        except Exception as e:
            print(f"❌ خطا در تحلیل قرارداد {address}: {str(e)}")
            return None

    def get_recent_contract_transactions(self, days_back=30, max_results=200):
        """دریافت تراکنش‌های اخیر ایجاد قرارداد"""
        try:
            contracts_found = []
            
            # دریافت آخرین بلاک
            latest_url = f"{self.base_url}?module=proxy&action=eth_blockNumber&apikey={self.etherscan_api_key}"
            latest_response = requests.get(latest_url)
            latest_data = latest_response.json()
            latest_block = int(latest_data['result'], 16)
            
            # تخمین بلاک شروع (حدود 15 ثانیه per block)
            blocks_back = days_back * 24 * 60 * 4  # تقریبی
            start_block = max(latest_block - blocks_back, 0)
            
            print(f"🔍 جستجو از بلاک {start_block} تا {latest_block}")
            
            # جستجو در چند بخش
            block_range = latest_block - start_block
            chunk_size = block_range // 10  # تقسیم به 10 قسمت
            
            for i in range(10):
                chunk_start = start_block + (i * chunk_size)
                chunk_end = min(chunk_start + chunk_size, latest_block)
                
                print(f"📦 پردازش بلاک‌های {chunk_start} تا {chunk_end}")
                
                # دریافت تراکنش‌ها
                tx_url = f"{self.base_url}?module=account&action=txlist&startblock={chunk_start}&endblock={chunk_end}&page=1&offset=50&sort=desc&apikey={self.etherscan_api_key}"
                
                tx_response = requests.get(tx_url)
                tx_data = tx_response.json()
                
                if tx_data.get('status') == '1' and tx_data.get('result'):
                    for tx in tx_data['result']:
                        if tx.get('to') == '' and len(contracts_found) < max_results:
                            # بررسی تاریخ
                            tx_timestamp = int(tx.get('timeStamp', 0))
                            if tx_timestamp >= self.start_timestamp:
                                
                                # دریافت آدرس قرارداد
                                receipt_url = f"{self.base_url}?module=proxy&action=eth_getTransactionReceipt&txhash={tx['hash']}&apikey={self.etherscan_api_key}"
                                receipt_response = requests.get(receipt_url)
                                receipt_data = receipt_response.json()
                                
                                if receipt_data.get('result') and receipt_data['result'].get('contractAddress'):
                                    contract_address = receipt_data['result']['contractAddress']
                                    
                                    contract_info = {
                                        'address': contract_address,
                                        'creator': tx['from'],
                                        'tx_hash': tx['hash'],
                                        'block_number': int(tx['blockNumber']),
                                        'timestamp': tx_timestamp,
                                        'date': datetime.fromtimestamp(tx_timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                                        'gas_used': int(tx.get('gasUsed', 0)),
                                        'gas_price': int(tx.get('gasPrice', 0))
                                    }
                                    
                                    contracts_found.append(contract_info)
                                    print(f"✅ قرارداد: {contract_address}")
                
                time.sleep(0.2)  # Rate limiting
                
                if len(contracts_found) >= max_results:
                    break
            
            return contracts_found
            
        except Exception as e:
            print(f"❌ خطا: {str(e)}")
            return []

    def analyze_contracts_batch(self, contracts):
        """تحلیل دسته‌ای قراردادها"""
        print(f"🔬 تحلیل {len(contracts)} قرارداد...")
        
        analyzed_contracts = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            
            for contract in contracts:
                future = executor.submit(self.analyze_contract, contract['address'])
                futures.append((future, contract))
            
            for future, original_contract in futures:
                try:
                    analysis = future.result(timeout=30)
                    if analysis:
                        # ترکیب اطلاعات اصلی با تحلیل
                        combined = {**original_contract, **analysis}
                        analyzed_contracts.append(combined)
                        
                        status = "✅ تایید شده" if analysis['is_verified'] else "❌ تایید نشده"
                        type_info = []
                        if analysis['is_token']:
                            type_info.append(f"توکن {analysis['token_standard']}")
                        if analysis['is_proxy']:
                            type_info.append("Proxy")
                        
                        type_str = f" ({', '.join(type_info)})" if type_info else ""
                        print(f"  {analysis['address']} - {status}{type_str}")
                        
                except Exception as e:
                    print(f"❌ خطا در تحلیل: {str(e)}")
                    analyzed_contracts.append(original_contract)
        
        return analyzed_contracts

    def generate_report(self, contracts):
        """تولید گزارش جامع"""
        if not contracts:
            print("😔 هیچ قراردادی برای گزارش یافت نشد")
            return
        
        print(f"\n📊 گزارش جامع قراردادهای هوشمند")
        print("=" * 50)
        
        # آمار کلی
        total = len(contracts)
        verified = sum(1 for c in contracts if c.get('is_verified'))
        tokens = sum(1 for c in contracts if c.get('is_token'))
        proxies = sum(1 for c in contracts if c.get('is_proxy'))
        
        print(f"📈 آمار کلی:")
        print(f"  کل قراردادها: {total}")
        print(f"  تایید شده: {verified} ({verified/total*100:.1f}%)")
        print(f"  توکن‌ها: {tokens} ({tokens/total*100:.1f}%)")
        print(f"  Proxy ها: {proxies} ({proxies/total*100:.1f}%)")
        
        # آمار توکن‌ها
        if tokens > 0:
            erc20 = sum(1 for c in contracts if c.get('token_standard') == 'ERC20')
            erc721 = sum(1 for c in contracts if c.get('token_standard') == 'ERC721')
            erc1155 = sum(1 for c in contracts if c.get('token_standard') == 'ERC1155')
            
            print(f"\n🪙 انواع توکن:")
            print(f"  ERC20: {erc20}")
            print(f"  ERC721 (NFT): {erc721}")
            print(f"  ERC1155: {erc1155}")
        
        # بزرگترین قراردادها
        large_contracts = sorted([c for c in contracts if c.get('bytecode_size', 0) > 0], 
                                key=lambda x: x.get('bytecode_size', 0), reverse=True)[:5]
        
        if large_contracts:
            print(f"\n🏗️ بزرگترین قراردادها (bytecode):")
            for i, contract in enumerate(large_contracts, 1):
                size_kb = contract.get('bytecode_size', 0) / 1000
                name = contract.get('contract_name', 'نامشخص')
                print(f"  {i}. {contract['address']} - {size_kb:.1f}KB ({name})")
        
        # ذخیره گزارش
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # JSON فایل
        json_filename = f"ethereum_contracts_report_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump({
                'search_period': {
                    'start_date': self.start_date.isoformat(),
                    'end_date': self.end_date.isoformat()
                },
                'statistics': {
                    'total_contracts': total,
                    'verified_contracts': verified,
                    'token_contracts': tokens,
                    'proxy_contracts': proxies
                },
                'contracts': contracts
            }, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n💾 گزارش کامل ذخیره شد: {json_filename}")

    def run(self):
        """اجرای جستجوی کامل"""
        print("🚀 شروع جستجوی پیشرفته قراردادهای هوشمند")
        
        # مرحله 1: دریافت قراردادهای اخیر
        contracts = self.get_recent_contract_transactions(days_back=31, max_results=100)
        
        if not contracts:
            print("😔 هیچ قراردادی یافت نشد")
            return
        
        print(f"✅ {len(contracts)} قرارداد یافت شد")
        
        # مرحله 2: تحلیل دقیق
        analyzed_contracts = self.analyze_contracts_batch(contracts)
        
        # مرحله 3: تولید گزارش
        self.generate_report(analyzed_contracts)

def main():
    print("=" * 60)
    print("🔍 Advanced Ethereum Smart Contracts Finder")
    print("جستجوگر پیشرفته قراردادهای هوشمند اتریوم")
    print("=" * 60)
    
    try:
        finder = AdvancedEthereumContractsFinder()
        finder.run()
        
    except KeyboardInterrupt:
        print("\n⏹️ عملیات متوقف شد")
    except Exception as e:
        print(f"❌ خطا: {str(e)}")

if __name__ == "__main__":
    main()
