import logging
from utils.logging_config import get_logger
from webhook.blockchain_utils import BlockchainUtils
from webhook.database_operations import DatabaseOperations
from webhook.notification_service import NotificationService
from datetime import datetime, timedelta
import time
import json
from sqlalchemy import text
from sqlalchemy.orm import Session

# تنظیم لاگر
logger = get_logger(__file__)

class TransactionProcessor:
    """
    کلاس اصلی برای پردازش تراکنش‌های بلاکچین که از وب‌هوک تاتوم دریافت می‌شوند.
    مسئولیت هماهنگی بین ماژول‌های مختلف برای پردازش وب‌هوک‌ها را دارد.
    """
    
    def __init__(self):
        """
        مقداردهی اولیه کلاس پردازشگر تراکنش
        """
        self.blockchain_utils = BlockchainUtils()
        self.db_operations = DatabaseOperations()
        self.notification_service = NotificationService()
        # ایجاد دیکشنری برای نگهداری رکورد تراکنش‌های اخیر
        # ساختار: {tx_id: {'timestamp': timestamp, 'count': count}}
        self.recently_processed_txs = {}
        # حداکثر زمان نگهداری رکورد تراکنش‌ها (30 دقیقه)
        self.tx_cache_expiry = 1800  # ثانیه
    
    def _normalize_transaction_value(self, value):
        """
        Normalize transaction value to a proper decimal format
        
        Args:
            value (str or float): Transaction value
            
        Returns:
            float: Normalized transaction value
        """
        try:
            # If value is already a float or int, return it directly
            if isinstance(value, (float, int)):
                return float(value)
                
            # If value is a string, try to convert it
            if isinstance(value, str):
                # Remove any commas
                value = value.replace(',', '')
                # Remove any non-numeric characters except dots and minus sign
                value = ''.join(c for c in value if c.isdigit() or c == '.' or c == '-')
                
                # Convert to float
                return float(value)
                
            # If value is None or other type
            return 0.0
            
        except (ValueError, TypeError) as e:
            logger.error(f"Error normalizing transaction value: {str(e)}")
            return 0.0
        
    def _clean_processed_tx_cache(self):
        """
        پاک کردن کش تراکنش‌های پردازش شده قدیمی
        """
        current_time = time.time()
        expired_txs = []
        
        for tx_id, tx_info in self.recently_processed_txs.items():
            if current_time - tx_info['timestamp'] > self.tx_cache_expiry:
                expired_txs.append(tx_id)
                
        for tx_id in expired_txs:
            self.recently_processed_txs.pop(tx_id, None)
            
        if expired_txs:
            logger.debug(f"تعداد {len(expired_txs)} رکورد قدیمی از کش تراکنش‌ها پاک شد")
    
    def process_webhook(self, webhook_data):
        """
        پردازش وب‌هوک دریافتی از تاتوم
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک
            
        Returns:
            dict: نتیجه پردازش
        """
        # بررسی داده‌های ورودی و ثبت در لاگ
        transaction_id = webhook_data.get('txId') or webhook_data.get('transactionId')
        transaction_type = webhook_data.get('type', '').lower()
        logger.info(f"📝 دریافت وب‌هوک برای تراکنش {transaction_id}, نوع: {transaction_type}")
        
        # بررسی سریع نوع تراکنش - اگر "fee" باشد نادیده می‌گیریم
        if transaction_type == 'fee':
            logger.info(f"⏭️ تراکنش {transaction_id} از نوع 'fee' است و پردازش نمی‌شود")
            return {"status": "نادیده گرفته شد", "reason": "تراکنش از نوع fee است"}
            
        # فقط تراکنش‌های با نوع "native", "token", و "" و "address_transaction" و "trc20" و "trc10" را پردازش می‌کنیم
        if transaction_type not in ['native', 'token', '', 'address_transaction', 'trc20', 'trc10']:
            logger.info(f"⏭️ تراکنش {transaction_id} از نوع '{transaction_type}' است و پردازش نمی‌شود")
            return {"status": "نادیده گرفته شد", "reason": f"تراکنش از نوع {transaction_type} است"}
            
        # استخراج اطلاعات اصلی
        blockchain = webhook_data.get('chain')
        # تبدیل نام بلاکچین تاتوم به فرمت داخلی ما
        blockchain = self.blockchain_utils.convert_chain_format(blockchain)
        
        if not transaction_id:
            logger.error("شناسه تراکنش در داده‌های وب‌هوک یافت نشد")
            return {"status": "خطا", "message": "شناسه تراکنش یافت نشد"}
        
        # بررسی تکراری بودن تراکنش
        self._clean_processed_tx_cache()  # پاک کردن کش رکوردهای قدیمی
        
        if transaction_id in self.recently_processed_txs:
            tx_info = self.recently_processed_txs[transaction_id]
            tx_info['count'] += 1
            logger.warning(f"⚠️ تراکنش {transaction_id} قبلاً پردازش شده است ({tx_info['count']} بار)")
            return {"status": "تکراری", "message": f"تراکنش قبلاً پردازش شده است ({tx_info['count']} بار)"}
        
        # افزودن به لیست تراکنش‌های اخیر
        self.recently_processed_txs[transaction_id] = {
            'timestamp': time.time(),
            'count': 1
        }
        
        logger.info(f"📝 پردازش وب‌هوک برای تراکنش {transaction_id} در {blockchain}")
        
        # تعیین نوع وب‌هوک و ارسال به پردازش مناسب
        webhook_type = webhook_data.get('type')
        subscription_type = webhook_data.get('subscriptionType')
        
        logger.info(f"نوع وب‌هوک: {webhook_type}، نوع اشتراک: {subscription_type}")
        
        # استخراج آدرس‌های فرستنده و گیرنده
        from_address = webhook_data.get('from')
        to_address = webhook_data.get('to') or webhook_data.get('counterAddress')
        
        # تنظیم آدرس‌ها برای وب‌هوک‌هایی که فیلد from ندارند
        if not from_address:
            # اگر counterAddress داریم و آدرس گیرنده (address) داریم
            if 'counterAddress' in webhook_data and 'address' in webhook_data:
                from_address = webhook_data.get('counterAddress')
                to_address = webhook_data.get('address')
                logger.info(f"استفاده از 'counterAddress' به عنوان آدرس فرستنده: {from_address}")
                logger.info(f"استفاده از 'address' به عنوان آدرس گیرنده: {to_address}")
            
            # اگر هنوز from_address تعیین نشده، سعی می‌کنیم از معیارهای دیگر استفاده کنیم
            elif 'address' in webhook_data:
                # بررسی نوع تراکنش و مقدار
                amount = webhook_data.get('amount', '0')
                try:
                    amount_value = float(amount)
                    if transaction_type == 'fee' or amount_value < 0:
                        # اگر کارمزد است یا مقدار منفی، از آدرس به عنوان فرستنده استفاده می‌کنیم
                        from_address = webhook_data.get('address')
                        logger.info(f"تشخیص آدرس فرستنده از نوع تراکنش '{transaction_type}': {from_address}")
                    elif amount_value > 0 and transaction_type == 'native':
                        # اگر native است و مقدار مثبت، address احتمالاً گیرنده است
                        to_address = webhook_data.get('address')
                        if 'counterAddress' in webhook_data:
                            from_address = webhook_data.get('counterAddress')
                        logger.info(f"تشخیص آدرس گیرنده از نوع تراکنش '{transaction_type}': {to_address}")
                        logger.info(f"تشخیص آدرس فرستنده از counterAddress: {from_address}")
                except (ValueError, TypeError):
                    logger.warning(f"مقدار نامعتبر: {amount}")
        
        value = webhook_data.get('value') or webhook_data.get('amount', '0')
        
        # اگر هنوز یکی از آدرس‌ها تعیین نشده باشد، هشدار می‌دهیم
        if not from_address or not to_address:
            logger.warning(f"⚠️ آدرس فرستنده یا گیرنده ناقص است - از: {from_address}, به: {to_address}")
            # در صورت نیاز می‌توانیم اینجا استراتژی دیگری برای تعیین آدرس‌ها اضافه کنیم
        
        logger.info(f"جزئیات تراکنش - از: {from_address}، به: {to_address}، مقدار: {value}، نوع: {webhook_type}")
        
        # پردازش بر اساس نوع
        if webhook_type == 'CONTRACT_LOG_EVENT' or subscription_type == 'CONTRACT_LOG_EVENT':
            # این یک رویداد قرارداد هوشمند است
            return self._process_contract_event(blockchain, webhook_data, transaction_id)
            
        elif webhook_type == 'ADDRESS_TRANSACTION' or subscription_type == 'ADDRESS_TRANSACTION' or webhook_type in ['native', 'token', 'trc20', 'trc10']:
            # این یک تراکنش آدرس کیف پول یا تراکنش ارز بومی یا توکن است
            return self._process_address_transaction(blockchain, from_address, to_address, value, transaction_id, webhook_data)
        
        else:
            logger.warning(f"نوع وب‌هوک/اشتراک پشتیبانی نشده: {webhook_type}/{subscription_type}")
            return {"status": "نادیده گرفته شد", "reason": "نوع وب‌هوک پشتیبانی نشده"}
    
    def _process_contract_event(self, blockchain, webhook_data, transaction_id):
        """
        پردازش رویدادهای قرارداد هوشمند
        
        Args:
            blockchain (str): نام بلاکچین
            webhook_data (dict): داده‌های وب‌هوک
            transaction_id (str): شناسه تراکنش
            
        Returns:
            dict: نتیجه پردازش
        """
        contract_address = webhook_data.get('address')
        log_events = webhook_data.get('logs', [])
        
        logger.info(f"رویداد قرارداد در {blockchain} برای قرارداد {contract_address}")
        logger.info(f"شناسه تراکنش: {transaction_id}")
        logger.debug(f"رویدادهای لاگ: {log_events}")
        
        # دریافت آدرس‌های کاربران از پایگاه داده
        user_addresses = self.db_operations.get_user_addresses()
        logger.debug(f"تعداد {len(user_addresses)} آدرس کاربر از پایگاه داده دریافت شد")
        
        # Filter addresses for current blockchain (with blockchain name normalization)
        blockchain_compare = blockchain.upper()
        
        # اصلاح برای پذیرش هر دو فرمت BSC و BNB
        user_blockchain_addresses = []
        for addr in user_addresses:
            addr_symbol = addr.get('currency_symbol', '').upper()
            # اگر بلاکچین BSC باشد، هم آدرس‌های BSC و هم BNB را بپذیریم
            if (blockchain_compare == 'BSC' and addr_symbol in ['BSC', 'BNB']) or \
               (blockchain_compare == 'BNB' and addr_symbol in ['BSC', 'BNB']) or \
               (addr_symbol == blockchain_compare):
                user_blockchain_addresses.append(addr)
        
        if not user_blockchain_addresses:
            logger.info(f"No user addresses found for blockchain {blockchain}")
            return {"status": "ignored", "reason": f"No user addresses for {blockchain}"}
        
        logger.info(f"تعداد {len(user_blockchain_addresses)} آدرس مرتبط با بلاکچین {blockchain} پیدا شد")
        
        # بررسی مرتبط بودن تراکنش با کاربران ما در این بلاکچین
        is_relevant = False
        relevant_addresses = []
        
        for log_idx, log in enumerate(log_events):
            # استخراج داده و عناوین از لاگ
            log_data = log.get('data', '')
            topics = log.get('topics', [])
            
            logger.debug(f"پردازش لاگ #{log_idx} با {len(topics)} عنوان")
            
            # بررسی حضور آدرس‌های کاربران ما در داده‌های لاگ
            for address_info in user_blockchain_addresses:
                public_address = address_info['public_address']
                if self.blockchain_utils.is_address_in_log(public_address, log_data, topics):
                    is_relevant = True
                    relevant_addresses.append(address_info)
                    logger.info(f"آدرس مرتبط {public_address} در داده‌های لاگ یافت شد (بلاکچین: {address_info.get('currency_symbol')})")
        
        if is_relevant:
            logger.info(f"تراکنش مرتبط با {len(relevant_addresses)} آدرس کاربر در بلاکچین {blockchain} یافت شد")
            
            # استخراج اطلاعات تکمیلی
            block_number = webhook_data.get('blockHeight')
            timestamp = webhook_data.get('timestamp')
            token_symbol = webhook_data.get('tokenSymbol') or webhook_data.get('asset')
            
            logger.debug(f"جزئیات تراکنش: بلاک: {block_number}، زمان: {timestamp}")
            
            # ذخیره تراکنش در جدول Transfers
            save_result = self.db_operations.save_transaction(
                blockchain=blockchain,
                transaction_id=transaction_id,
                relevant_addresses=relevant_addresses,
                webhook_data=webhook_data,
                block_number=block_number,
                timestamp=timestamp,
                token_symbol=token_symbol,
                token_contract=contract_address
            )
            
            if save_result:
                logger.info(f"تراکنش {transaction_id} با موفقیت در جدول Transfers ذخیره شد")
                
                # به‌روزرسانی موجودی کیف پول‌ها
                for address_info in relevant_addresses:
                    logger.debug(f"به‌روزرسانی موجودی برای آدرس {address_info['public_address']}")
                    self.db_operations.update_wallet_balance(address_info, blockchain)
                
                # ارسال اعلان به فرانت‌اند
                self.notification_service.notify(
                    transaction_type='contract_event',
                    transaction_id=transaction_id,
                    relevant_addresses=relevant_addresses,
                    webhook_data=webhook_data
                )
                
                return {"status": "پردازش شد", "relevant": True, "saved": True}
            else:
                logger.error(f"خطا در ذخیره تراکنش {transaction_id} در جدول Transfers")
                return {"status": "خطا", "relevant": True, "saved": False, "message": "خطا در ذخیره تراکنش"}
        else:
            logger.info(f"تراکنش برای هیچ یک از کاربران ما در بلاکچین {blockchain} مرتبط نیست")
            return {"status": "نادیده گرفته شد", "relevant": False}
    
    def _process_address_transaction(self, blockchain, from_address, to_address, value, transaction_id, webhook_data):
        """
        Process a transaction between addresses
        
        Args:
            blockchain (str): Blockchain name
            from_address (str): Sender address
            to_address (str): Receiver address
            value (str): Transaction value
            transaction_id (str): Transaction ID
            webhook_data (dict): Webhook data
            
        Returns:
            dict: Processing result
        """
        logger.info(f"Processing address transaction on {blockchain} from {from_address} to {to_address}")
        
        # Get user addresses in this blockchain
        user_addresses = self.db_operations.get_user_addresses()
        if not user_addresses:
            logger.warning("No user addresses found in the database")
            return {"status": "ignored", "reason": "No user addresses found"}
        
        # Filter addresses for current blockchain (with blockchain name normalization)
        blockchain_compare = blockchain.upper()
        
        # اصلاح برای پذیرش هر دو فرمت BSC و BNB
        user_blockchain_addresses = []
        for addr in user_addresses:
            addr_symbol = addr.get('currency_symbol', '').upper()
            # اگر بلاکچین BSC باشد، هم آدرس‌های BSC و هم BNB را بپذیریم
            if (blockchain_compare == 'BSC' and addr_symbol in ['BSC', 'BNB']) or \
               (blockchain_compare == 'BNB' and addr_symbol in ['BSC', 'BNB']) or \
               (addr_symbol == blockchain_compare):
                user_blockchain_addresses.append(addr)
        
        if not user_blockchain_addresses:
            logger.info(f"No user addresses found for blockchain {blockchain}")
            return {"status": "ignored", "reason": f"No user addresses for {blockchain}"}
            
        # بررسی آیا این تراکنش مربوط به توکن اتریوم است
        is_eth_token = False
        chain = webhook_data.get('chain', '').lower()
        tx_type = webhook_data.get('type')
        
        if (blockchain.upper() == 'ETH' or 'ethereum' in chain) and tx_type == 'token':
            is_eth_token = True
            logger.info("تراکنش توکن اتریوم شناسایی شد")
            
        # اگر جهت تراکنش قبلاً تنظیم شده، از آن استفاده می‌کنیم
        predefined_direction = webhook_data.get('direction')
        if predefined_direction:
            logger.info(f"استفاده از جهت تراکنش پیش‌تنظیم شده: {predefined_direction}")
        
        # تعیین آدرس‌های فرستنده و گیرنده بر اساس نوع تراکنش
        real_from_address = ""
        real_to_address = ""
        
        # اگر این تراکنش اتریوم است، مستقیماً از فیلدهای from و to استفاده می‌کنیم
        if 'from' in webhook_data and 'to' in webhook_data and (webhook_data.get('from') and webhook_data.get('to')):
            real_from_address = webhook_data.get('from')
            real_to_address = webhook_data.get('to')
            logger.info(f"استفاده از آدرس‌های from و to در webhook_data - از: {real_from_address}, به: {real_to_address}")
        # اگر توکن اتریوم است، از address و counterAddress استفاده می‌کنیم
        elif is_eth_token:
            real_from_address = webhook_data.get('address')
            real_to_address = webhook_data.get('counterAddress')
            logger.info(f"تنظیم آدرس‌ها برای توکن اتریوم - از: {real_from_address} به: {real_to_address}")
        # در غیر این صورت از مقادیر معمول counterAddress و address استفاده می‌کنیم
        else:
            real_from_address = webhook_data.get('counterAddress', '')
            real_to_address = webhook_data.get('address', '')
            logger.info(f"استفاده از مقادیر معمول - از: {real_from_address}, به: {real_to_address}")
        
        # اگر هنوز آدرس‌ها مشکل دارند، از پارامترهای تابع استفاده می‌کنیم
        if (not real_from_address or not real_to_address or real_from_address == real_to_address):
            if from_address and to_address:
                real_from_address = from_address
                real_to_address = to_address
                logger.info(f"استفاده از پارامترهای تابع - از: {real_from_address}, به: {real_to_address}")
        
        logger.info(f"آدرس‌های نهایی: از {real_from_address} به {real_to_address}")
            
        # Normalize addresses for comparison
        from_address_norm = real_from_address.lower() if real_from_address else ""
        to_address_norm = real_to_address.lower() if real_to_address else ""
        
        # Check if this transaction is relevant to any user address
        is_relevant = False
        
        # Determine transaction direction
        direction = predefined_direction  # اگر از قبل تنظیم شده از آن استفاده می‌کنیم
        user_public_address = None
        
        logger.info(f"Checking {len(user_blockchain_addresses)} addresses for relevance to transaction {transaction_id}")
        
        # First check if the transaction involves any of our user addresses
        for addr_info in user_blockchain_addresses:
            user_addr = addr_info.get('public_address', '').lower()
            logger.debug(f"Comparing user address {user_addr} with from={from_address_norm}, to={to_address_norm}")
            
            if user_addr and from_address_norm and user_addr == from_address_norm:
                # User address is sending - outbound transaction
                is_relevant = True
                if direction is None:  # فقط اگر جهت قبلاً تنظیم نشده باشد
                    direction = "outbound"
                user_public_address = user_addr
                logger.info(f"Transaction direction: OUTBOUND - User {user_addr} is sending")
                break
                
            if user_addr and to_address_norm and user_addr == to_address_norm:
                # User address is receiving - inbound transaction
                is_relevant = True
                if direction is None:  # فقط اگر جهت قبلاً تنظیم نشده باشد
                    direction = "inbound"
                user_public_address = user_addr
                logger.info(f"Transaction direction: INBOUND - User {user_addr} is receiving")
                break
        
        # If transaction is not relevant to our users, ignore it
        if not is_relevant:
            logger.info(f"Transaction {transaction_id} is not relevant to any user address")
            return {"status": "ignored", "reason": "Not relevant to any user address"}
            
        # اگر توکن اتریوم است و کاربر مالک آدرس اصلی (address) است، جهت تراکنش outbound است
        if is_eth_token and user_public_address and user_public_address == webhook_data.get('address', '').lower():
            direction = "outbound"
            logger.info(f"تنظیم جهت تراکنش توکن اتریوم به outbound برای کاربر {user_public_address}")
        
        try:
            amount = self._normalize_transaction_value(value)
            address_id = None
            wallet_id = None
            
            # Find the AddressID and WalletID from our database
            for addr_info in user_blockchain_addresses:
                if addr_info.get('public_address', '').lower() == user_public_address:
                    address_id = addr_info.get('address_id')
                    wallet_id = addr_info.get('wallet_id')
                    break
            
            if not address_id or not wallet_id:
                logger.error(f"Failed to find AddressID or WalletID for address {user_public_address}")
                return {"status": "error", "message": "Address or wallet ID not found"}
            
            # For tokens, get additional info
            token_symbol = webhook_data.get('symbol') or webhook_data.get('tokenSymbol') or webhook_data.get('asset')
            asset_type = "native"
            token_contract = None
            
            if webhook_data.get('type') == 'token' or webhook_data.get('type') == 'trc20' or webhook_data.get('type') == 'trc10':
                asset_type = "token"
                token_contract = webhook_data.get('tokenAddress') or webhook_data.get('contractAddress')
                
                # Special handling for TRC20 tokens where asset might be the contract address
                if blockchain.upper() in ['TRX', 'TRON'] and webhook_data.get('asset') and webhook_data.get('asset').startswith('T') and len(webhook_data.get('asset')) > 30:
                    # This is likely a contract address in the asset field
                    contract_address = webhook_data.get('asset')
                    token_contract = contract_address
                    
                    # Check known tokens map for TRC20
                    known_tokens = {
                        'T9yYp7JUxypLk7GFhsLRj5jN6ZrNDcH2Cf': 'NCC',
                        'TCDgp5bwtixaShPifUm7HpZ71C1pe6zif1': 'NCC',
                        'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t': 'USDT',
                        'TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8': 'USDC',
                    }
                    
                    if contract_address in known_tokens:
                        token_symbol = known_tokens[contract_address]
                        logger.info(f"Mapped TRC20 contract {contract_address} to token symbol {token_symbol}")
                
                # If token_symbol is not provided but we have a contract address
                if not token_symbol and token_contract:
                    # Try to get token symbol from database using contract address
                    try:
                        with Session(self.db_operations._get_engine()) as db_session:
                            token_query = text("""
                                SELECT Symbol FROM currencies 
                                WHERE LOWER(SmartContractAddress) = LOWER(:contract_address)
                                LIMIT 1
                            """)
                            
                            result = db_session.execute(token_query, {'contract_address': token_contract}).fetchone()
                            if result:
                                token_symbol = result[0]
                                logger.info(f"Found token symbol {token_symbol} for contract {token_contract}")
                            else:
                                # اگر در ترون هستیم، بررسی می‌کنیم که آیا این توکن در `known_tokens` وجود دارد
                                if blockchain.upper() == 'TRX' or blockchain.upper() == 'TRON':
                                    known_tokens = {
                                        'T9yYp7JUxypLk7GFhsLRj5jN6ZrNDcH2Cf': 'NCC',
                                        'TCDgp5bwtixaShPifUm7HpZ71C1pe6zif1': 'NCC',
                                        'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t': 'USDT',
                                        'TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8': 'USDC',
                                    }
                                    
                                    if token_contract in known_tokens:
                                        token_symbol = known_tokens[token_contract]
                                        logger.info(f"Using predefined token symbol {token_symbol} for contract {token_contract}")
                                    else:
                                        # جستجوی فازی برای یافتن توکن با اسمارت کانترکت مشابه
                                        fuzzy_query = text("""
                                            SELECT Symbol FROM currencies 
                                            WHERE SmartContractAddress LIKE :contract_address_pattern
                                            LIMIT 1
                                        """)
                                        
                                        contract_pattern = f"%{token_contract}%"
                                        fuzzy_result = db_session.execute(fuzzy_query, {'contract_address_pattern': contract_pattern}).fetchone()
                                        
                                        if fuzzy_result:
                                            token_symbol = fuzzy_result[0]
                                            logger.info(f"Found token symbol {token_symbol} with fuzzy matching for contract {token_contract}")
                                        else:
                                            logger.warning("Token transaction without symbol, using UNKNOWN symbol")
                                            token_symbol = 'UNKNOWN'  # استفاده از UNKNOWN به جای آدرس قرارداد
                                else:
                                    # If we still don't have a symbol, use UNKNOWN as symbol
                                    logger.warning("Token transaction without symbol, using UNKNOWN symbol")
                                    token_symbol = 'UNKNOWN'  # استفاده از UNKNOWN به جای آدرس قرارداد
                    except Exception as e:
                        logger.error(f"Error querying token symbol: {str(e)}")
                        token_symbol = 'UNKNOWN'  # استفاده از UNKNOWN به جای آدرس قرارداد
            
            # If token_symbol starts with 0x and is long, it's likely a contract address
            if token_symbol and (token_symbol.startswith('0x') or token_symbol.startswith('0X')) and len(token_symbol) >= 40:
                # If we haven't set the token_contract yet, use this as the contract
                if not token_contract:
                    token_contract = token_symbol
                    asset_type = "token"  # Since we have a contract address, it's a token
                # استفاده از UNKNOWN به جای آدرس قرارداد
                token_symbol = 'UNKNOWN'
                logger.warning(f"Token symbol is a contract address, replacing with UNKNOWN")
            
            # Construct relevant_addresses for save_transaction
            relevant_addresses = [{
                'address_id': address_id,
                'wallet_id': wallet_id,
                'public_address': user_public_address,
                'direction': direction,
                'currency_symbol': token_symbol or blockchain
            }]
            
            # Extract price and fee from webhook_data if available
            price = webhook_data.get('price')
            fee = webhook_data.get('fee')
            
            # Log for debugging
            if price:
                logger.info(f"Price extracted from webhook data: ${price}")
            if fee:
                logger.info(f"Fee extracted from webhook data: {fee} {blockchain}")
            
            # Save transaction to database
            save_result = self.db_operations.save_transaction(
                blockchain=blockchain,
                transaction_id=transaction_id,
                relevant_addresses=relevant_addresses,
                webhook_data=webhook_data,
                block_number=webhook_data.get('blockNumber'),
                timestamp=webhook_data.get('timestamp'),
                from_address=real_from_address,  # استفاده از آدرس‌های اصلاح شده
                to_address=real_to_address,      # استفاده از آدرس‌های اصلاح شده
                token_contract=token_contract,   # اضافه کردن token_contract به پارامترهای ارسالی
                price=price,                     # اضافه کردن قیمت به پارامترهای ارسالی
                fee=fee                          # اضافه کردن کارمزد به پارامترهای ارسالی
            )
            
            if save_result:
                logger.info(f"Transaction {transaction_id} successfully saved to database")
                
                # تبدیل TRON به TRX قبل از به‌روزرسانی موجودی
                if token_symbol and token_symbol.upper() == 'TRON':
                    token_symbol = 'TRX'
                    logger.info(f"Converted token symbol from TRON to TRX for consistency")
                    
                if blockchain.upper() in ['TRON', 'TRX']:
                    blockchain = 'TRX'
                    logger.info(f"Standardized blockchain name to TRX")
                    
                # اگر ارز بلاکچین native است و سمبل آن تنظیم نشده، از نام بلاکچین استفاده می‌کنیم
                if asset_type == 'native' and not token_symbol:
                    token_symbol = blockchain
                    logger.info(f"Set token symbol to blockchain name: {blockchain} for native asset")
                
                # Update wallet balance
                if token_symbol and token_contract and asset_type == "token":
                    # For tokens
                    self.db_operations.update_wallet_balance(
                        address_info={'address_id': address_id, 'wallet_id': wallet_id, 'public_address': user_public_address},
                        blockchain=blockchain,
                        token_contract=token_contract,
                        token_symbol=token_symbol
                    )
                    
                    # Standardize token symbol for TRX/TRON before updating user holding
                    if blockchain.upper() in ['TRX', 'TRON']:
                        if token_symbol and token_symbol.upper() in ['TRON', 'TRX']:
                            token_symbol = 'TRX'
                        blockchain = 'TRX'
                        
                    # Update user holding balance in database for tokens
                    self.db_operations.update_user_holding_balance(
                        wallet_id=wallet_id,
                        blockchain=blockchain,
                        token_symbol=token_symbol,
                        direction=direction,
                        amount=amount,
                        tx_id=transaction_id,
                        contract_address=token_contract
                    )
                else:
                    # For native coins
                    self.db_operations.update_wallet_balance(
                        address_info={'address_id': address_id, 'wallet_id': wallet_id, 'public_address': user_public_address},
                        blockchain=blockchain,
                        token_symbol=token_symbol or blockchain
                    )
                    
                    # Standardize token symbol for TRX/TRON before updating user holding
                    if blockchain.upper() in ['TRX', 'TRON']:
                        if token_symbol and token_symbol.upper() in ['TRON', 'TRX']:
                            token_symbol = 'TRX'
                        blockchain = 'TRX'
                        
                    # Update user holding balance in database for native coins
                    self.db_operations.update_user_holding_balance(
                        wallet_id=wallet_id,
                        blockchain=blockchain,
                        token_symbol=token_symbol or blockchain,
                        direction=direction,
                        amount=amount,
                        tx_id=transaction_id
                    )
                
                # Send notification
                self.notification_service.notify(
                    transaction_type='address_transaction',
                    transaction_id=transaction_id,
                    relevant_addresses=relevant_addresses,
                    webhook_data=webhook_data
                )
                
                return {
                    "status": "success",
                    "transaction_id": transaction_id,
                    "direction": direction,
                    "amount": amount,
                    "token": token_symbol or blockchain
                }
            else:
                logger.error(f"Error saving transaction {transaction_id} to database")
                return {"status": "error", "message": "Error saving transaction to database"}
                
        except Exception as e:
            logger.error(f"Error processing transaction {transaction_id}: {str(e)}")
            logger.exception(e)
            return {"status": "error", "message": str(e)}
    
    def update_transaction(self, blockchain, tx_hash):
        """
        به‌روزرسانی دستی اطلاعات تراکنش
        
        Args:
            blockchain (str): نماد بلاکچین
            tx_hash (str): هش تراکنش
            
        Returns:
            dict: نتیجه به‌روزرسانی
        """
        try:
            # دریافت جزئیات تراکنش از تاتوم
            tx_details = self.blockchain_utils.get_transaction_details(tx_hash, blockchain)
            
            if not tx_details:
                return {"status": "خطا", "message": "جزئیات تراکنش یافت نشد"}
            
            logger.info(f"به‌روزرسانی وضعیت تراکنش {tx_hash} در جدول Transfers")
            
            # به‌روزرسانی اطلاعات در پایگاه داده
            result = self.db_operations.update_transaction_status(tx_hash, blockchain, tx_details)
            
            if result.get("success"):
                return {
                    "status": "موفق", 
                    "message": "تراکنش در جدول Transfers به‌روزرسانی شد",
                    "details": result
                }
            else:
                logger.warning(f"خطا در به‌روزرسانی تراکنش: {result.get('error')}")
                return {
                    "status": "خطا", 
                    "message": f"خطا در به‌روزرسانی: {result.get('error')}",
                    "details": result
                }
            
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی تراکنش {tx_hash}: {str(e)}")
            return {"status": "خطا", "message": str(e)} 