import logging
import re
import json
from typing import Optional, Dict, Any, Tuple

class AddressParser:
    """
    Class responsible for parsing blockchain addresses from webhook data
    """
    
    def __init__(self, config):
        """
        Initialize the AddressParser
        
        Args:
            config (dict): Application configuration
        """
        self.config = config
        self.logger = logging.getLogger('webhook.address_parser')
        self.logger.info("🚀 AddressParser initialized")
        
        # Blockchain address patterns and validation rules
        self.address_patterns = {
            'BTC': r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}$',
            'ETH': r'^0x[a-fA-F0-9]{40}$',
            'BSC': r'^0x[a-fA-F0-9]{40}$',
            'MATIC': r'^0x[a-fA-F0-9]{40}$',
            'TRON': r'^T[a-zA-Z0-9]{33}$',
            'SOL': r'^[1-9A-HJ-NP-Za-km-z]{32,44}$',
            'XRP': r'^r[0-9a-zA-Z]{24,34}$',
            'DOGE': r'^D{1}[5-9A-HJ-NP-U]{1}[1-9A-HJ-NP-Za-km-z]{32}$',
            'ADA': r'^(addr1|stake1)[0-9a-z]{98}$',
            'AVAX': r'^X-[a-zA-Z0-9]{39}$',
            'ATOM': r'^cosmos[0-9a-z]{38,45}$',
            'DOT': r'^[1-9A-HJ-NP-Za-km-z]{46,48}$',
            'NEAR': r'^[0-9a-z.]{2,64}\.near$',
            'ALGO': r'^[A-Z2-7]{58}$',
            'FTM': r'^0x[a-fA-F0-9]{40}$',
            'ONE': r'^one1[a-z0-9]{38}$'
        }
    
    def parse_transaction_addresses(self, 
                                    blockchain: str, 
                                    tx_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse sender and recipient addresses from transaction data
        
        Args:
            blockchain (str): Blockchain name (e.g., 'ETH', 'BTC')
            tx_data (dict): Transaction data from webhook
            
        Returns:
            tuple: (sender_address, recipient_address)
        """
        try:
            sender_address = None
            recipient_address = None
            
            blockchain = blockchain.upper()
            
            # Parse based on blockchain type
            if blockchain in ['ETH', 'BSC', 'MATIC', 'FTM']:
                # EVM-compatible chains
                sender_address = self._parse_evm_sender(tx_data)
                recipient_address = self._parse_evm_recipient(tx_data)
            elif blockchain == 'BTC':
                # Bitcoin
                sender_address = self._parse_btc_sender(tx_data)
                recipient_address = self._parse_btc_recipient(tx_data)
            elif blockchain == 'TRON':
                # Tron
                sender_address = self._parse_tron_sender(tx_data)
                recipient_address = self._parse_tron_recipient(tx_data)
            elif blockchain == 'SOL':
                # Solana
                sender_address = self._parse_solana_sender(tx_data)
                recipient_address = self._parse_solana_recipient(tx_data)
            else:
                # Generic fallback
                sender_address = self._parse_generic_sender(tx_data)
                recipient_address = self._parse_generic_recipient(tx_data)
            
            # Validate addresses
            if sender_address and not self._validate_address(blockchain, sender_address):
                self.logger.warning(f"⚠️ Invalid {blockchain} sender address format: {sender_address}")
                sender_address = None
            
            if recipient_address and not self._validate_address(blockchain, recipient_address):
                self.logger.warning(f"⚠️ Invalid {blockchain} recipient address format: {recipient_address}")
                recipient_address = None
            
            return sender_address, recipient_address
            
        except Exception as e:
            self.logger.error(f"⛔ Error parsing transaction addresses: {str(e)}", exc_info=True)
            return None, None
    
    def _validate_address(self, blockchain: str, address: str) -> bool:
        """
        Validate an address format based on the blockchain
        
        Args:
            blockchain (str): Blockchain name
            address (str): Address to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not address:
            return False
            
        blockchain = blockchain.upper()
        
        # If blockchain not in defined patterns, return True (no validation)
        if blockchain not in self.address_patterns:
            return True
            
        pattern = self.address_patterns[blockchain]
        return bool(re.match(pattern, address))
    
    def _parse_evm_sender(self, tx_data: Dict[str, Any]) -> Optional[str]:
        """Parse sender address from EVM transaction data"""
        try:
            # Try common fields where sender might be found
            if 'from' in tx_data:
                return tx_data['from']
            elif 'sender' in tx_data:
                return tx_data['sender']
            elif 'fromAddress' in tx_data:
                return tx_data['fromAddress']
            
            # Check in nested objects
            if 'transaction' in tx_data and 'from' in tx_data['transaction']:
                return tx_data['transaction']['from']
                
            return None
        except Exception as e:
            self.logger.error(f"Error parsing EVM sender: {str(e)}")
            return None
    
    def _parse_evm_recipient(self, tx_data: Dict[str, Any]) -> Optional[str]:
        """Parse recipient address from EVM transaction data"""
        try:
            # Try common fields where recipient might be found
            if 'to' in tx_data:
                return tx_data['to']
            elif 'recipient' in tx_data:
                return tx_data['recipient']
            elif 'toAddress' in tx_data:
                return tx_data['toAddress']
            
            # Check in nested objects
            if 'transaction' in tx_data and 'to' in tx_data['transaction']:
                return tx_data['transaction']['to']
                
            return None
        except Exception as e:
            self.logger.error(f"Error parsing EVM recipient: {str(e)}")
            return None
    
    def _parse_btc_sender(self, tx_data: Dict[str, Any]) -> Optional[str]:
        """Parse sender address from Bitcoin transaction data"""
        try:
            # Try to get sender from inputs
            if 'inputs' in tx_data and tx_data['inputs'] and len(tx_data['inputs']) > 0:
                for input_data in tx_data['inputs']:
                    if 'address' in input_data:
                        return input_data['address']
            
            # Try common fields
            if 'from' in tx_data:
                return tx_data['from']
            elif 'sender' in tx_data:
                return tx_data['sender']
                
            return None
        except Exception as e:
            self.logger.error(f"Error parsing BTC sender: {str(e)}")
            return None
    
    def _parse_btc_recipient(self, tx_data: Dict[str, Any]) -> Optional[str]:
        """Parse recipient address from Bitcoin transaction data"""
        try:
            # Try to get recipient from outputs
            if 'outputs' in tx_data and tx_data['outputs'] and len(tx_data['outputs']) > 0:
                for output_data in tx_data['outputs']:
                    if 'address' in output_data:
                        return output_data['address']
            
            # Try common fields
            if 'to' in tx_data:
                return tx_data['to']
            elif 'recipient' in tx_data:
                return tx_data['recipient']
                
            return None
        except Exception as e:
            self.logger.error(f"Error parsing BTC recipient: {str(e)}")
            return None
    
    def _parse_tron_sender(self, tx_data: Dict[str, Any]) -> Optional[str]:
        """Parse sender address from Tron transaction data"""
        try:
            # Handle common Tron format
            if 'ownerAddress' in tx_data:
                return tx_data['ownerAddress']
            elif 'from' in tx_data:
                return tx_data['from']
            elif 'owneraddress' in tx_data:
                return tx_data['owneraddress']
                
            return None
        except Exception as e:
            self.logger.error(f"Error parsing Tron sender: {str(e)}")
            return None
    
    def _parse_tron_recipient(self, tx_data: Dict[str, Any]) -> Optional[str]:
        """Parse recipient address from Tron transaction data"""
        try:
            # Handle common Tron format
            if 'toAddress' in tx_data:
                return tx_data['toAddress']
            elif 'to' in tx_data:
                return tx_data['to']
            elif 'toaddress' in tx_data:
                return tx_data['toaddress']
            
            # Check contract transfer
            if 'contract_address' in tx_data and 'to' in tx_data:
                return tx_data['to']
                
            return None
        except Exception as e:
            self.logger.error(f"Error parsing Tron recipient: {str(e)}")
            return None
    
    def _parse_solana_sender(self, tx_data: Dict[str, Any]) -> Optional[str]:
        """Parse sender address from Solana transaction data"""
        try:
            # Try common Solana fields
            if 'feePayer' in tx_data:
                return tx_data['feePayer']
            elif 'owner' in tx_data:
                return tx_data['owner']
            elif 'from' in tx_data:
                return tx_data['from']
            
            # Try to get from account keys
            if 'accountKeys' in tx_data and len(tx_data['accountKeys']) > 0:
                return tx_data['accountKeys'][0]
                
            return None
        except Exception as e:
            self.logger.error(f"Error parsing Solana sender: {str(e)}")
            return None
    
    def _parse_solana_recipient(self, tx_data: Dict[str, Any]) -> Optional[str]:
        """Parse recipient address from Solana transaction data"""
        try:
            # Try common Solana fields
            if 'to' in tx_data:
                return tx_data['to']
            elif 'destination' in tx_data:
                return tx_data['destination']
            
            # Try to get from account keys
            if 'accountKeys' in tx_data and len(tx_data['accountKeys']) > 1:
                return tx_data['accountKeys'][1]
                
            return None
        except Exception as e:
            self.logger.error(f"Error parsing Solana recipient: {str(e)}")
            return None
    
    def _parse_generic_sender(self, tx_data: Dict[str, Any]) -> Optional[str]:
        """Generic fallback for sender address parsing"""
        try:
            # Try common field names
            for field in ['from', 'sender', 'fromAddress', 'source', 'owner', 'ownerAddress']:
                if field in tx_data:
                    return tx_data[field]
            
            # Try to find in nested objects
            if 'transaction' in tx_data:
                for field in ['from', 'sender', 'fromAddress']:
                    if field in tx_data['transaction']:
                        return tx_data['transaction'][field]
                        
            return None
        except Exception as e:
            self.logger.error(f"Error in generic sender parsing: {str(e)}")
            return None
    
    def _parse_generic_recipient(self, tx_data: Dict[str, Any]) -> Optional[str]:
        """Generic fallback for recipient address parsing"""
        try:
            # Try common field names
            for field in ['to', 'recipient', 'toAddress', 'destination', 'target']:
                if field in tx_data:
                    return tx_data[field]
            
            # Try to find in nested objects
            if 'transaction' in tx_data:
                for field in ['to', 'recipient', 'toAddress']:
                    if field in tx_data['transaction']:
                        return tx_data['transaction'][field]
                        
            return None
        except Exception as e:
            self.logger.error(f"Error in generic recipient parsing: {str(e)}")
            return None
    
    def process_tatum_transaction(self, transaction_data, blockchain):
        """
        پردازش داده‌های تراکنش دریافتی از Tatum
        
        Args:
            transaction_data (dict): داده‌های تراکنش
            blockchain (str): نام بلاکچین
            
        Returns:
            dict: دیکشنری حاوی آدرس‌های مرتبط و اطلاعات توکن
        """
        self.logger.info(f"🔄 شروع پردازش تراکنش {blockchain}: {transaction_data.get('txId', 'unknown')}")
        
        if not transaction_data:
            self.logger.error("⛔ داده‌های تراکنش خالی است")
            return None
            
        # استخراج اطلاعات اساسی تراکنش
        result = {
            'transaction_id': transaction_data.get('txId'),
            'block_number': transaction_data.get('blockNumber'),
            'timestamp': transaction_data.get('timestamp'),
            'blockchain': blockchain,
            'from_addresses': [],
            'to_addresses': [],
            'contract_address': None,
            'token_symbol': None,
            'token_id': None,
            'token_name': None,
            'amount': None,
            'transaction_type': 'TRANSFER',  # مقدار پیش‌فرض
        }
        
        try:
            # پردازش بر اساس نوع بلاکچین
            if blockchain.lower() in ['eth', 'ethereum', 'polygon', 'bsc']:
                self._process_evm_transaction(transaction_data, result)
            elif blockchain.lower() in ['btc', 'bitcoin']:
                self._process_bitcoin_transaction(transaction_data, result)
            # اضافه کردن پشتیبانی از بلاکچین‌های دیگر در آینده
            else:
                self.logger.warning(f"⚠️ بلاکچین {blockchain} هنوز پشتیبانی نمی‌شود")
                return None
                
            self.logger.info(f"✅ پردازش تراکنش {result['transaction_id']} با موفقیت انجام شد")
            self.logger.debug(f"جزئیات استخراج شده: {json.dumps(result, ensure_ascii=False)}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"⛔ خطا در پردازش تراکنش: {str(e)}", exc_info=True)
            return None
    
    def _process_evm_transaction(self, transaction_data, result):
        """
        پردازش تراکنش‌های EVM (اتریوم، پالیگان، BSC)
        
        Args:
            transaction_data (dict): داده‌های تراکنش
            result (dict): دیکشنری نتیجه برای تکمیل
        """
        self.logger.debug(f"پردازش تراکنش EVM: {transaction_data.get('txId')}")
        
        # بررسی نوع تراکنش (عادی یا تراکنش قرارداد هوشمند)
        if 'tokenTransfers' in transaction_data and transaction_data['tokenTransfers']:
            # تراکنش توکن ERC-20 یا ERC-721
            self._process_token_transfer(transaction_data, result)
        else:
            # تراکنش عادی
            self._process_native_transfer(transaction_data, result)
            
        # ثبت نتیجه پردازش
        self.logger.debug(f"نتیجه پردازش EVM: {len(result['from_addresses'])} آدرس مبدا، {len(result['to_addresses'])} آدرس مقصد")
    
    def _process_token_transfer(self, transaction_data, result):
        """
        پردازش انتقال توکن (ERC-20/ERC-721)
        
        Args:
            transaction_data (dict): داده‌های تراکنش
            result (dict): دیکشنری نتیجه برای تکمیل
        """
        token_transfers = transaction_data.get('tokenTransfers', [])
        self.logger.debug(f"پردازش {len(token_transfers)} انتقال توکن")
        
        for token_transfer in token_transfers:
            # استخراج اطلاعات توکن
            result['contract_address'] = token_transfer.get('contractAddress')
            result['token_symbol'] = token_transfer.get('symbol')
            result['token_name'] = token_transfer.get('name')
            
            # تشخیص نوع توکن (ERC-20 یا ERC-721)
            if 'tokenId' in token_transfer:
                result['token_id'] = token_transfer.get('tokenId')
                result['transaction_type'] = 'NFT_TRANSFER'
                self.logger.debug(f"تشخیص انتقال NFT با توکن آیدی {result['token_id']}")
            else:
                result['transaction_type'] = 'TOKEN_TRANSFER'
                self.logger.debug(f"تشخیص انتقال توکن {result['token_symbol']}")
            
            # استخراج آدرس‌ها
            from_address = token_transfer.get('from')
            to_address = token_transfer.get('to')
            amount = token_transfer.get('value', '0')
            
            if from_address and from_address not in result['from_addresses']:
                result['from_addresses'].append(from_address)
                self.logger.debug(f"افزودن آدرس مبدا: {from_address}")
                
            if to_address and to_address not in result['to_addresses']:
                result['to_addresses'].append(to_address)
                self.logger.debug(f"افزودن آدرس مقصد: {to_address}")
                
            result['amount'] = amount
    
    def _process_native_transfer(self, transaction_data, result):
        """
        پردازش انتقال ارز اصلی بلاکچین
        
        Args:
            transaction_data (dict): داده‌های تراکنش
            result (dict): دیکشنری نتیجه برای تکمیل
        """
        # استخراج آدرس‌های اصلی
        from_address = transaction_data.get('from')
        to_address = transaction_data.get('to')
        amount = transaction_data.get('value', '0')
        
        if from_address and from_address not in result['from_addresses']:
            result['from_addresses'].append(from_address)
            self.logger.debug(f"افزودن آدرس مبدا برای انتقال ارز اصلی: {from_address}")
            
        if to_address and to_address not in result['to_addresses']:
            result['to_addresses'].append(to_address)
            self.logger.debug(f"افزودن آدرس مقصد برای انتقال ارز اصلی: {to_address}")
            
        # تعیین نماد توکن بر اساس بلاکچین
        if result['blockchain'].lower() == 'eth' or result['blockchain'].lower() == 'ethereum':
            result['token_symbol'] = 'ETH'
        elif result['blockchain'].lower() == 'polygon':
            result['token_symbol'] = 'MATIC'
        elif result['blockchain'].lower() == 'bsc':
            result['token_symbol'] = 'BNB'
            
        result['amount'] = amount
        result['transaction_type'] = 'NATIVE_TRANSFER'
        self.logger.debug(f"تشخیص انتقال ارز اصلی {result['token_symbol']} به مقدار {amount}")
    
    def _process_bitcoin_transaction(self, transaction_data, result):
        """
        پردازش تراکنش‌های بیت‌کوین
        
        Args:
            transaction_data (dict): داده‌های تراکنش
            result (dict): دیکشنری نتیجه برای تکمیل
        """
        self.logger.debug(f"پردازش تراکنش بیت‌کوین: {transaction_data.get('txId')}")
        
        # تنظیم نماد توکن
        result['token_symbol'] = 'BTC'
        result['transaction_type'] = 'NATIVE_TRANSFER'
        
        # استخراج آدرس‌های ورودی
        if 'inputs' in transaction_data:
            for input_data in transaction_data['inputs']:
                if 'address' in input_data and input_data['address'] not in result['from_addresses']:
                    result['from_addresses'].append(input_data['address'])
                    self.logger.debug(f"افزودن آدرس ورودی بیت‌کوین: {input_data['address']}")
        
        # استخراج آدرس‌های خروجی
        if 'outputs' in transaction_data:
            total_amount = 0
            for output_data in transaction_data['outputs']:
                if 'address' in output_data and output_data['address'] not in result['to_addresses']:
                    result['to_addresses'].append(output_data['address'])
                    self.logger.debug(f"افزودن آدرس خروجی بیت‌کوین: {output_data['address']}")
                
                # محاسبه مجموع مقادیر
                if 'value' in output_data:
                    total_amount += float(output_data.get('value', 0))
            
            result['amount'] = str(total_amount)
            self.logger.debug(f"مجموع مقدار تراکنش بیت‌کوین: {total_amount}")
            
    def normalize_address(self, address, blockchain):
        """
        نرمال‌سازی آدرس برای سازگاری با فرمت‌های مختلف
        
        Args:
            address (str): آدرس اصلی
            blockchain (str): نام بلاکچین
            
        Returns:
            str: آدرس نرمال‌سازی شده
        """
        if not address:
            return None
            
        try:
            # نرمال‌سازی آدرس‌های EVM به صورت lowercase
            if blockchain.lower() in ['eth', 'ethereum', 'polygon', 'bsc']:
                normalized = address.lower()
                self.logger.debug(f"نرمال‌سازی آدرس EVM: {address} -> {normalized}")
                return normalized
                
            # نرمال‌سازی آدرس‌های بیت‌کوین (فعلاً بدون تغییر)
            return address
            
        except Exception as e:
            self.logger.error(f"⛔ خطا در نرمال‌سازی آدرس {address}: {str(e)}")
            return address
    
    def is_valid_address(self, address, blockchain):
        """
        بررسی اعتبار فرمت آدرس
        
        Args:
            address (str): آدرس برای بررسی
            blockchain (str): نام بلاکچین
            
        Returns:
            bool: نتیجه اعتبارسنجی
        """
        if not address:
            return False
            
        try:
            # الگوهای اعتبارسنجی آدرس‌های مختلف
            patterns = {
                'eth': r'^0x[a-fA-F0-9]{40}$',  # آدرس اتریوم / بلاکچین‌های EVM
                'btc': r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[ac-hj-np-z02-9]{11,71}$'  # آدرس‌های بیت‌کوین (legacy و segwit)
            }
            
            # انتخاب الگوی مناسب
            if blockchain.lower() in ['eth', 'ethereum', 'polygon', 'bsc']:
                pattern = patterns['eth']
            elif blockchain.lower() in ['btc', 'bitcoin']:
                pattern = patterns['btc']
            else:
                self.logger.warning(f"⚠️ الگوی اعتبارسنجی برای بلاکچین {blockchain} یافت نشد")
                return True  # فرض می‌کنیم آدرس معتبر است
                
            # بررسی انطباق با الگو
            is_valid = bool(re.match(pattern, address))
            
            if not is_valid:
                self.logger.warning(f"⚠️ آدرس {address} بر اساس الگوی {blockchain} معتبر نیست")
                
            return is_valid
            
        except Exception as e:
            self.logger.error(f"⛔ خطا در اعتبارسنجی آدرس {address}: {str(e)}")
            return False  # در صورت خطا، فرض می‌کنیم آدرس نامعتبر است 