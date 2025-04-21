import logging
import json
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

from webhook.address_parser import AddressParser
from webhook.balance_updater import BalanceUpdater
from models.tx_record import TxRecord
from models.event_log import EventLog
from utils.db_operations import DBOperations

class TatumWebhookProcessor:
    """
    کلاس پردازش وب‌هوک‌های دریافتی از Tatum
    """
    
    def __init__(self, config, session_factory):
        """
        مقداردهی اولیه کلاس
        
        Args:
            config (dict): تنظیمات سیستم
            session_factory: تابع ایجادکننده نشست دیتابیس
        """
        self.config = config
        self.session_factory = session_factory
        self.db_operations = DBOperations(session_factory)
        self.address_parser = AddressParser(config)
        self.balance_updater = BalanceUpdater(config, self.db_operations)
        self.logger = logging.getLogger('webhook.processor')
        self.logger.info("🚀 مقداردهی اولیه TatumWebhookProcessor")
    
    def process_webhook(self, webhook_data):
        """
        پردازش داده‌های وب‌هوک دریافتی
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک
            
        Returns:
            dict: نتیجه پردازش به صورت دیکشنری
        """
        if not webhook_data:
            self.logger.error("⛔ داده‌های وب‌هوک خالی است")
            return {
                'success': False,
                'message': 'داده‌های وب‌هوک خالی است',
                'data': None
            }
            
        try:
            self.logger.info(f"🔄 شروع پردازش وب‌هوک: {webhook_data.get('txId', 'unknown')}")
            self.logger.debug(f"داده‌های دریافتی: {json.dumps(webhook_data, ensure_ascii=False)}")
            
            # ثبت رویداد دریافت وب‌هوک
            self._log_webhook_event(webhook_data)
            
            # استخراج بلاکچین
            blockchain = webhook_data.get('currency', '').upper()
            if not blockchain:
                self.logger.error("⛔ اطلاعات بلاکچین در داده‌های وب‌هوک موجود نیست")
                return {
                    'success': False,
                    'message': 'اطلاعات بلاکچین موجود نیست',
                    'data': None
                }
                
            # پردازش تراکنش
            transaction_info = self.address_parser.process_tatum_transaction(webhook_data, blockchain)
            if not transaction_info:
                self.logger.error("⛔ خطا در پردازش تراکنش")
                return {
                    'success': False,
                    'message': 'خطا در پردازش تراکنش',
                    'data': None
                }
                
            # بررسی آدرس‌های تراکنش و بروزرسانی موجودی کیف پول‌ها
            processing_result = self._process_transaction(transaction_info)
            
            self.logger.info(f"✅ پردازش وب‌هوک {webhook_data.get('txId', 'unknown')} با موفقیت انجام شد")
            
            return {
                'success': True,
                'message': 'پردازش وب‌هوک با موفقیت انجام شد',
                'data': processing_result
            }
            
        except Exception as e:
            self.logger.error(f"⛔ خطا در پردازش وب‌هوک: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'خطای داخلی: {str(e)}',
                'data': None
            }
    
    def _process_transaction(self, transaction_info):
        """
        پردازش اطلاعات تراکنش و بروزرسانی موجودی کیف پول‌ها
        
        Args:
            transaction_info (dict): اطلاعات تراکنش پردازش شده
            
        Returns:
            dict: نتیجه پردازش
        """
        try:
            # ذخیره سابقه تراکنش در دیتابیس
            tx_id = self._save_transaction_record(transaction_info)
            self.logger.info(f"💾 سابقه تراکنش با شناسه داخلی {tx_id} ذخیره شد")
            
            # پردازش آدرس‌های مرتبط
            affected_wallets = []
            
            # پردازش آدرس‌های مبدا (برداشت از کیف پول)
            for from_address in transaction_info.get('from_addresses', []):
                wallet_id = self._find_wallet_by_address(from_address, transaction_info['blockchain'])
                if wallet_id:
                    self.logger.info(f"🔍 آدرس {from_address} متعلق به کیف پول {wallet_id} است")
                    # بروزرسانی موجودی (برداشت)
                    update_result = self.balance_updater.update_wallet_balance(
                        wallet_id=wallet_id,
                        blockchain=transaction_info['blockchain'],
                        token_symbol=transaction_info['token_symbol'],
                        contract_address=transaction_info.get('contract_address'),
                        amount=transaction_info['amount'],
                        direction='outbound',
                        tx_id=transaction_info['transaction_id']
                    )
                    
                    if update_result['success']:
                        affected_wallets.append({
                            'wallet_id': wallet_id,
                            'address': from_address,
                            'direction': 'outbound',
                            'amount': transaction_info['amount'],
                            'balance_updated': True
                        })
                    else:
                        self.logger.error(f"⛔ خطا در بروزرسانی موجودی کیف پول {wallet_id}: {update_result['message']}")
            
            # پردازش آدرس‌های مقصد (واریز به کیف پول)
            for to_address in transaction_info.get('to_addresses', []):
                wallet_id = self._find_wallet_by_address(to_address, transaction_info['blockchain'])
                if wallet_id:
                    self.logger.info(f"🔍 آدرس {to_address} متعلق به کیف پول {wallet_id} است")
                    # بروزرسانی موجودی (واریز)
                    update_result = self.balance_updater.update_wallet_balance(
                        wallet_id=wallet_id,
                        blockchain=transaction_info['blockchain'],
                        token_symbol=transaction_info['token_symbol'],
                        contract_address=transaction_info.get('contract_address'),
                        amount=transaction_info['amount'],
                        direction='inbound',
                        tx_id=transaction_info['transaction_id']
                    )
                    
                    if update_result['success']:
                        affected_wallets.append({
                            'wallet_id': wallet_id,
                            'address': to_address,
                            'direction': 'inbound',
                            'amount': transaction_info['amount'],
                            'balance_updated': True
                        })
                    else:
                        self.logger.error(f"⛔ خطا در بروزرسانی موجودی کیف پول {wallet_id}: {update_result['message']}")
            
            return {
                'transaction_id': transaction_info['transaction_id'],
                'internal_tx_id': tx_id,
                'affected_wallets': affected_wallets,
                'transaction_type': transaction_info['transaction_type'],
                'token_symbol': transaction_info['token_symbol'],
                'amount': transaction_info['amount']
            }
            
        except Exception as e:
            self.logger.error(f"⛔ خطا در پردازش تراکنش: {str(e)}", exc_info=True)
            return {
                'transaction_id': transaction_info.get('transaction_id', 'unknown'),
                'error': str(e),
                'affected_wallets': []
            }
    
    def _find_wallet_by_address(self, address, blockchain):
        """
        یافتن کیف پول با استفاده از آدرس
        
        Args:
            address (str): آدرس بلاکچین
            blockchain (str): نام بلاکچین
            
        Returns:
            str: شناسه کیف پول یا None در صورت عدم یافتن
        """
        try:
            # نرمال‌سازی آدرس
            normalized_address = self.address_parser.normalize_address(address, blockchain)
            
            # جستجوی آدرس در دیتابیس
            with self.session_factory() as session:
                wallet_address = self.db_operations.find_wallet_address(
                    session=session,
                    address=normalized_address,
                    blockchain=blockchain
                )
                
                if wallet_address:
                    return wallet_address.wallet_id
                    
                self.logger.debug(f"آدرس {normalized_address} در بلاکچین {blockchain} متعلق به هیچ کیف پولی نیست")
                return None
                
        except Exception as e:
            self.logger.error(f"⛔ خطا در جستجوی کیف پول برای آدرس {address}: {str(e)}", exc_info=True)
            return None
    
    def _save_transaction_record(self, transaction_info):
        """
        ذخیره سابقه تراکنش در دیتابیس
        
        Args:
            transaction_info (dict): اطلاعات تراکنش
            
        Returns:
            int: شناسه داخلی رکورد تراکنش
        """
        try:
            with self.session_factory() as session:
                # بررسی وجود تراکنش در دیتابیس
                existing_tx = self.db_operations.find_transaction_by_tx_id(
                    session=session,
                    tx_id=transaction_info['transaction_id'],
                    blockchain=transaction_info['blockchain']
                )
                
                if existing_tx:
                    self.logger.info(f"تراکنش {transaction_info['transaction_id']} قبلاً در دیتابیس ثبت شده است")
                    return existing_tx.id
                
                # ایجاد رکورد جدید تراکنش در TxRecord
                tx_record = TxRecord(
                    tx_id=transaction_info['transaction_id'],
                    blockchain=transaction_info['blockchain'],
                    block_number=transaction_info.get('block_number'),
                    tx_timestamp=transaction_info.get('timestamp'),
                    from_addresses=json.dumps(transaction_info.get('from_addresses', [])),
                    to_addresses=json.dumps(transaction_info.get('to_addresses', [])),
                    amount=transaction_info.get('amount', '0'),
                    token_symbol=transaction_info.get('token_symbol'),
                    token_name=transaction_info.get('token_name'),
                    contract_address=transaction_info.get('contract_address'),
                    token_id=transaction_info.get('token_id'),
                    tx_type=transaction_info.get('transaction_type', 'TRANSFER'),
                    created_at=datetime.now()
                )
                
                session.add(tx_record)
                session.flush()  # فلاش برای دریافت شناسه بدون کامیت کامل
                
                # اکنون تراکنش را در جدول Transfers نیز ذخیره می‌کنیم
                self.logger.info(f"ذخیره تراکنش {transaction_info['transaction_id']} در جدول Transfers")
                
                # دریافت شناسه بلاکچین برای ذخیره در جدول Transfers
                blockchain_id = self.db_operations._get_blockchain_id(session, transaction_info['blockchain'])
                if not blockchain_id:
                    self.logger.error(f"⛔ بلاکچین {transaction_info['blockchain']} در دیتابیس یافت نشد")
                    session.rollback()
                    return None
                
                # ذخیره تراکنش برای هر آدرس مرتبط
                for from_address in transaction_info.get('from_addresses', []):
                    wallet_id = self._find_wallet_by_address(from_address, transaction_info['blockchain'])
                    if wallet_id:
                        # پیدا کردن شناسه آدرس از دیتابیس
                        address_record = self.db_operations.find_wallet_address(
                            session=session,
                            address=from_address,
                            blockchain=transaction_info['blockchain']
                        )
                        
                        if address_record:
                            # ذخیره تراکنش خروجی در جدول Transfers
                            try:
                                self._save_transfer_record(
                                    session=session,
                                    blockchain_id=blockchain_id,
                                    address_id=address_record.AddressID,
                                    wallet_id=wallet_id,
                                    tx_hash=transaction_info['transaction_id'],
                                    block_number=transaction_info.get('block_number'),
                                    timestamp=transaction_info.get('timestamp'),
                                    from_address=from_address,
                                    to_address=transaction_info.get('to_addresses', [None])[0],
                                    amount=transaction_info.get('amount', '0'),
                                    token_symbol=transaction_info.get('token_symbol'),
                                    token_contract=transaction_info.get('contract_address'),
                                    asset_type=self._determine_asset_type(transaction_info),
                                    direction='outbound'
                                )
                            except Exception as e:
                                self.logger.error(f"⛔ خطا در ذخیره تراکنش در Transfers برای آدرس {from_address}: {str(e)}", exc_info=True)
                
                for to_address in transaction_info.get('to_addresses', []):
                    wallet_id = self._find_wallet_by_address(to_address, transaction_info['blockchain'])
                    if wallet_id:
                        # پیدا کردن شناسه آدرس از دیتابیس
                        address_record = self.db_operations.find_wallet_address(
                            session=session,
                            address=to_address,
                            blockchain=transaction_info['blockchain']
                        )
                        
                        if address_record:
                            # ذخیره تراکنش ورودی در جدول Transfers
                            try:
                                self._save_transfer_record(
                                    session=session,
                                    blockchain_id=blockchain_id,
                                    address_id=address_record.AddressID,
                                    wallet_id=wallet_id,
                                    tx_hash=transaction_info['transaction_id'],
                                    block_number=transaction_info.get('block_number'),
                                    timestamp=transaction_info.get('timestamp'),
                                    from_address=transaction_info.get('from_addresses', [None])[0],
                                    to_address=to_address,
                                    amount=transaction_info.get('amount', '0'),
                                    token_symbol=transaction_info.get('token_symbol'),
                                    token_contract=transaction_info.get('contract_address'),
                                    asset_type=self._determine_asset_type(transaction_info),
                                    direction='inbound'
                                )
                            except Exception as e:
                                self.logger.error(f"⛔ خطا در ذخیره تراکنش در Transfers برای آدرس {to_address}: {str(e)}", exc_info=True)
                
                # کامیت تغییرات
                session.commit()
                
                self.logger.info(f"تراکنش با شناسه {tx_record.id} در دیتابیس ثبت شد")
                return tx_record.id
                
        except SQLAlchemyError as e:
            self.logger.error(f"⛔ خطای دیتابیس در ذخیره تراکنش: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(f"⛔ خطا در ذخیره سابقه تراکنش: {str(e)}", exc_info=True)
            raise
    
    def _save_transfer_record(self, session, blockchain_id, address_id, wallet_id, tx_hash, block_number, 
                             timestamp, from_address, to_address, amount, token_symbol, token_contract, 
                             asset_type, direction):
        """
        ذخیره رکورد تراکنش در جدول Transfers
        
        Args:
            session: نشست دیتابیس
            blockchain_id (int): شناسه بلاکچین
            address_id (int): شناسه آدرس
            wallet_id (str): شناسه کیف پول
            tx_hash (str): هش تراکنش
            block_number (int): شماره بلاک
            timestamp (str): زمان تراکنش
            from_address (str): آدرس فرستنده
            to_address (str): آدرس گیرنده
            amount (str): مقدار تراکنش
            token_symbol (str): نماد توکن
            token_contract (str): آدرس قرارداد توکن
            asset_type (str): نوع دارایی (native/token)
            direction (str): جهت تراکنش (inbound/outbound)
        """
        from database.Transfers import Transfers
        
        # تبدیل timestamp به datetime اگر رشته است
        tx_time = timestamp
        if isinstance(timestamp, str):
            try:
                tx_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                tx_time = datetime.now()
        elif timestamp is None:
            tx_time = datetime.now()
        
        # ایجاد رکورد Transfers
        transfer = Transfers(
            BlockchainID=blockchain_id,
            AddressID=address_id,
            WalletID=wallet_id,
            TxHash=tx_hash,
            BlockNumber=block_number,
            Timestamp=tx_time,
            FromAddress=from_address,
            ToAddress=to_address,
            Amount=amount,
            TokenSymbol=token_symbol,
            TokenContract=token_contract,
            AssetType=asset_type,
            Direction=direction,
            Status='confirmed',
            IsSuccessful=True,
            CreatedAt=datetime.now(),
            UpdatedAt=datetime.now()
        )
        
        session.add(transfer)
        self.logger.debug(f"رکورد انتقال برای تراکنش {tx_hash} با جهت {direction} ایجاد شد")
    
    def _determine_asset_type(self, transaction_info):
        """
        تعیین نوع دارایی بر اساس اطلاعات تراکنش
        
        Args:
            transaction_info (dict): اطلاعات تراکنش
            
        Returns:
            str: 'native' یا 'token'
        """
        # اگر contract_address وجود داشته باشد، یک توکن است
        if transaction_info.get('contract_address'):
            return 'token'
        
        # اگر نوع تراکنش مشخص کند که توکن است
        if transaction_info.get('transaction_type') in ['TOKEN_TRANSFER', 'NFT_TRANSFER']:
            return 'token'
        
        # بررسی اگر token_symbol متفاوت از نماد ارز اصلی بلاکچین باشد
        token_symbol = transaction_info.get('token_symbol', '')
        blockchain = transaction_info.get('blockchain', '').upper()
        
        native_tokens = {
            'ETH': ['ETH'],
            'BSC': ['BNB'],
            'POLYGON': ['MATIC'],
            'AVAX': ['AVAX'],
            'BTC': ['BTC'],
            'TRX': ['TRX'],
            'SOL': ['SOL']
        }
        
        if token_symbol and blockchain in native_tokens:
            if token_symbol.upper() not in native_tokens[blockchain]:
                return 'token'
        
        # پیش‌فرض: ارز بومی
        return 'native'
    
    def _log_webhook_event(self, webhook_data):
        """
        ثبت رویداد دریافت وب‌هوک در دیتابیس
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک
        """
        try:
            with self.session_factory() as session:
                event_log = EventLog(
                    event_type='WEBHOOK_RECEIVED',
                    data=json.dumps(webhook_data, ensure_ascii=False),
                    created_at=datetime.now()
                )
                
                session.add(event_log)
                session.commit()
                
                self.logger.debug(f"رویداد وب‌هوک با شناسه {event_log.id} در دیتابیس ثبت شد")
                
        except Exception as e:
            self.logger.error(f"⛔ خطا در ثبت رویداد وب‌هوک: {str(e)}", exc_info=True)
            # این خطا نباید باعث توقف پردازش شود، بنابراین فقط لاگ می‌شود 