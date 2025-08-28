from CC.webhook.transaction_processor import TransactionProcessor
from CC.utils.logging_config import get_logger
from CC.webhook.chains.bnb.utils import parse_bnb_input_data, calculate_bnb_fee, is_token_transfer

logger = get_logger(__name__)

class BNBProcessor(TransactionProcessor):
    """پردازشگر وب‌هوک‌های مخصوص Binance Smart Chain (BNB)"""
    
    def __init__(self):
        super().__init__()
        logger.info("پردازشگر Binance Smart Chain راه‌اندازی شد")
    
    def process_webhook(self, webhook_data):
        """
        پردازش وب‌هوک Binance Smart Chain
        این متد منطق خاص BSC را اجرا می‌کند
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک دریافتی
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info("پردازش وب‌هوک Binance Smart Chain")
        
        # نرمال‌سازی داده‌های وب‌هوک
        self._normalize_webhook_data(webhook_data)
        
        # بررسی داده‌های ورودی تراکنش برای تشخیص نوع عملیات
        input_data = webhook_data.get('input')
        if input_data and len(input_data) > 10:
            parsed_data = parse_bnb_input_data(input_data)
            webhook_data['bnb_input_data'] = parsed_data
            
            # بررسی نوع تراکنش
            if parsed_data.get('type') == 'token_transfer':
                logger.info(f"تراکنش انتقال توکن BEP-20 شناسایی شد: {webhook_data.get('hash', '')}")
                
                # افزودن اطلاعات توکن به داده‌های وب‌هوک
                contract_address = webhook_data.get('to')
                if contract_address:
                    webhook_data['token_contract'] = contract_address
                    
                # اینجا می‌توان تنظیمات خاص توکن‌های BEP-20 را اضافه کرد
                # مثلاً دریافت نام توکن، نماد و تعداد اعشار
        
        # محاسبه کارمزد تراکنش
        if 'gasPrice' in webhook_data and 'gasUsed' in webhook_data:
            try:
                gas_price = webhook_data.get('gasPrice')
                gas_used = webhook_data.get('gasUsed')
                fee = calculate_bnb_fee(gas_price, gas_used)
                webhook_data['fee'] = fee
                logger.info(f"کارمزد محاسبه شده برای تراکنش: {fee} BNB")
            except Exception as e:
                logger.error(f"خطا در محاسبه کارمزد: {str(e)}")
        
        # تنظیم نوع دارایی (توکن یا ارز اصلی)
        if is_token_transfer(webhook_data.get('input', '')):
            webhook_data['asset_type'] = 'token'
        else:
            webhook_data['asset_type'] = 'native'
        
        # افزودن اطلاعات تکمیلی به داده‌های وب‌هوک
        webhook_data['chain'] = 'binance smart chain'
        if 'currency' not in webhook_data:
            webhook_data['currency'] = 'bnb'
            
        # فراخوانی پردازشگر اصلی
        return super().process_webhook(webhook_data)
    
    def _normalize_webhook_data(self, webhook_data):
        """
        نرمال‌سازی داده‌های وب‌هوک بایننس
        بعضی از فیلدها در وب‌هوک بایننس ممکن است با فرمت‌های مختلف ارسال شوند
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک دریافتی
        """
        # استاندارد کردن نام‌های فیلدها
        field_mappings = {
            'txid': 'hash',
            'transactionHash': 'hash',
            'blockNumber': 'blockNumber',
            'blockHash': 'blockHash',
            'fromAddress': 'from',
            'from_address': 'from',
            'toAddress': 'to',
            'to_address': 'to',
            'value': 'amount'
        }
        
        for old_field, new_field in field_mappings.items():
            if old_field in webhook_data and new_field not in webhook_data:
                webhook_data[new_field] = webhook_data[old_field]
        
        # اطمینان از وجود مقدار در فرمت صحیح
        if 'amount' in webhook_data and isinstance(webhook_data['amount'], str):
            try:
                # تبدیل مقدار به عدد اعشاری
                amount = float(webhook_data['amount'])
                
                # اگر مقدار برای BNB در واحد wei است، آن را به BNB تبدیل کنیم
                if amount > 1e10:  # احتمالاً در واحد wei است
                    amount = amount / 1e18
                    webhook_data['amount'] = str(amount)
            except (ValueError, TypeError):
                pass
    
    def update_transaction(self, blockchain, tx_hash):
        """
        به‌روزرسانی تراکنش بایننس
        
        Args:
            blockchain (str): نام بلاکچین
            tx_hash (str): هش تراکنش
            
        Returns:
            dict: نتیجه به‌روزرسانی
        """
        logger.info(f"به‌روزرسانی تراکنش بایننس: {tx_hash}")
        
        # اینجا می‌توان منطق خاص به‌روزرسانی BSC را اضافه کرد
        # مثلاً استعلام جزئیات بیشتر از یک API خارجی
        
        # فراخوانی متد اصلی
        return super().update_transaction(blockchain, tx_hash)
        
    def _process_address_transaction(self, blockchain, from_address, to_address, value, transaction_id, webhook_data):
        """
        پردازش تراکنش آدرس بایننس
        
        Args:
            blockchain (str): نام بلاکچین
            from_address (str): آدرس فرستنده
            to_address (str): آدرس گیرنده
            value (str): مقدار تراکنش
            transaction_id (str): شناسه تراکنش
            webhook_data (dict): داده‌های کامل وب‌هوک
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info(f"پردازش تراکنش آدرس بایننس: {transaction_id}")
        
        # تشخیص نوع تراکنش (توکن یا ارز اصلی)
        is_token = webhook_data.get('asset_type') == 'token'
        
        # اگر تراکنش توکن است، آدرس قرارداد را استخراج کنیم
        contract_address = None
        token_symbol = 'BNB'
        
        if is_token:
            contract_address = webhook_data.get('token_contract')
            # اینجا می‌توان از یک سرویس خارجی برای دریافت نماد توکن استفاده کرد
            # یا از database_operations.get_token_symbol_from_contract استفاده کرد
            token_symbol = webhook_data.get('token_symbol', 'BEP20')
            
            # در صورت نیاز، استخراج آدرس گیرنده واقعی از داده‌های تراکنش
            if 'bnb_input_data' in webhook_data and webhook_data['bnb_input_data'].get('type') == 'token_transfer':
                # استخراج آدرس گیرنده از داده‌های ورودی - نیاز به پیاده‌سازی جداگانه دارد
                pass
        
        # ایجاد دیکشنری نتیجه
        result = {
            'transaction_id': transaction_id,
            'blockchain': blockchain,
            'from_address': from_address,
            'to_address': to_address,
            'amount': value,
            'token_symbol': token_symbol,
            'is_token': is_token,
            'contract_address': contract_address,
            'status': 'confirmed'
        }
        
        # فراخوانی متد اصلی
        return super()._process_address_transaction(blockchain, from_address, to_address, value, transaction_id, webhook_data)
    
    def _process_contract_event(self, blockchain, webhook_data, transaction_id):
        """
        پردازش رویداد قرارداد بایننس
        
        Args:
            blockchain (str): نام بلاکچین
            webhook_data (dict): داده‌های وب‌هوک
            transaction_id (str): شناسه تراکنش
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info(f"پردازش رویداد قرارداد بایننس: {transaction_id}")
        
        # اینجا می‌توان منطق خاص پردازش رویدادهای BEP-20 را اضافه کرد
        
        # فراخوانی متد اصلی
        return super()._process_contract_event(blockchain, webhook_data, transaction_id) 