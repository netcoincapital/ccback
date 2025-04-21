from webhook.transaction_processor import TransactionProcessor
from utils.logging_config import get_logger
from webhook.chains.eth.utils import parse_eth_input_data

logger = get_logger(__name__)

class EthereumProcessor(TransactionProcessor):
    """پردازشگر وب‌هوک‌های مخصوص اتریوم"""
    
    def __init__(self):
        super().__init__()
        logger.info("پردازشگر اتریوم راه‌اندازی شد")
    
    def process_webhook(self, webhook_data):
        """
        پردازش وب‌هوک اتریوم
        این متد می‌تواند منطق خاص اتریوم را اجرا کند
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک دریافتی
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info("پردازش وب‌هوک اتریوم")
        
        # تعیین نوع تراکنش و مشخص کردن فرستنده و گیرنده
        tx_type = webhook_data.get('type')
        chain = webhook_data.get('chain', '').lower()
        
        if tx_type and chain and 'ethereum' in chain:
            if tx_type == 'native':
                # در تراکنش‌های native، counterAddress فرستنده و address گیرنده است
                from_address = webhook_data.get('counterAddress')
                to_address = webhook_data.get('address')
                
                # تنظیم مستقیم فیلدهای مورد نیاز
                webhook_data['from'] = from_address
                webhook_data['to'] = to_address
                
                logger.debug(f"تراکنش native: فرستنده {from_address}, گیرنده {to_address}")
                
            elif tx_type == 'token':
                # در تراکنش‌های token، address فرستنده و counterAddress گیرنده است
                from_address = webhook_data.get('address')
                to_address = webhook_data.get('counterAddress')
                
                # تنظیم مستقیم فیلدهای مورد نیاز
                webhook_data['from'] = from_address
                webhook_data['to'] = to_address
                webhook_data['direction'] = 'outbound'  # جهت تراکنش خروجی است
                
                # اطمینان از تنظیم token_contract برای تراکنش‌های توکن
                token_contract = webhook_data.get('asset')
                if token_contract and token_contract.startswith('0x') and len(token_contract) >= 40:
                    webhook_data['tokenContract'] = token_contract
                    # همچنین در فیلد‌های استاندارد هم تنظیم می‌کنیم
                    webhook_data['contractAddress'] = token_contract
                    webhook_data['tokenAddress'] = token_contract
                    logger.info(f"تنظیم آدرس قرارداد توکن: {token_contract}")
                
                logger.info(f"تراکنش token اتریوم: از {from_address} به {to_address}")
        
        # بررسی داده‌های ورودی تراکنش برای تشخیص نوع عملیات (فقط برای تراکنش‌های قرارداد هوشمند)
        input_data = webhook_data.get('input')
        if input_data and len(input_data) > 10:
            parsed_data = parse_eth_input_data(input_data)
            method_id = parsed_data.get('method_id')
            logger.debug(f"شناسه متد تراکنش: {method_id}")
            
            # اینجا می‌توانید منطق خاص برای هر نوع متد را اضافه کنید
            # مثلاً تشخیص تراکنش‌های swap، approve، transfer و غیره
        
        # افزودن اطلاعات تکمیلی به داده‌های وب‌هوک
        webhook_data['chain'] = 'ethereum'
        if 'currency' not in webhook_data:
            webhook_data['currency'] = 'eth'
        
        # چاپ وضعیت نهایی داده‌ها قبل از ارسال به TransactionProcessor
        logger.info(f"وضعیت نهایی داده‌های وب‌هوک اتریوم قبل از پردازش:")
        logger.info(f"type: {webhook_data.get('type')}")
        logger.info(f"chain: {webhook_data.get('chain')}")
        logger.info(f"from: {webhook_data.get('from')}")
        logger.info(f"to: {webhook_data.get('to')}")
        logger.info(f"direction: {webhook_data.get('direction', 'تنظیم نشده')}")
        logger.info(f"asset/token: {webhook_data.get('asset')}")
        logger.info(f"tokenContract: {webhook_data.get('tokenContract')}")
        
        # فراخوانی پردازشگر اصلی
        return super().process_webhook(webhook_data)
    
    def update_transaction(self, blockchain, tx_hash):
        """
        به‌روزرسانی تراکنش اتریوم
        
        Args:
            blockchain (str): نام بلاکچین
            tx_hash (str): هش تراکنش
            
        Returns:
            dict: نتیجه به‌روزرسانی
        """
        logger.info(f"به‌روزرسانی تراکنش اتریوم: {tx_hash}")
        
        # فراخوانی متد اصلی
        return super().update_transaction(blockchain, tx_hash) 