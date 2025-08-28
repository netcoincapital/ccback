from CC.webhook.transaction_processor import TransactionProcessor
from CC.utils.logging_config import get_logger
from CC.webhook.chains.eth.utils import parse_eth_input_data  # استفاده از همان توابع اتریوم چون سازگار است

logger = get_logger(__name__)

class PolygonProcessor(TransactionProcessor):
    """پردازشگر وب‌هوک‌های مخصوص پالیگان (ماتیک)"""
    
    def __init__(self):
        super().__init__()
        logger.info("پردازشگر پالیگان (ماتیک) راه‌اندازی شد")
    
    def process_webhook(self, webhook_data):
        """
        پردازش وب‌هوک پالیگان
        این متد می‌تواند منطق خاص پالیگان را اجرا کند
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک دریافتی
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info("پردازش وب‌هوک پالیگان")
        
        # بررسی داده‌های ورودی تراکنش (مشابه با اتریوم)
        input_data = webhook_data.get('input')
        if input_data and len(input_data) > 10:
            parsed_data = parse_eth_input_data(input_data)
            webhook_data['polygon_input_data'] = parsed_data
            
            # اینجا می‌توانید منطق خاص پالیگان را اضافه کنید
        
        # افزودن اطلاعات کارمزد پالیگان - معمولاً بسیار کمتر از اتریوم است
        if 'gasPrice' in webhook_data and 'gasUsed' in webhook_data:
            try:
                gas_price = float(webhook_data['gasPrice'])
                gas_used = float(webhook_data['gasUsed'])
                fee = gas_price * gas_used
                webhook_data['fee'] = fee
                logger.info(f"کارمزد محاسبه شده برای تراکنش پالیگان: {fee} MATIC")
            except Exception as e:
                logger.error(f"خطا در محاسبه کارمزد پالیگان: {str(e)}")
        
        # افزودن اطلاعات تکمیلی به داده‌های وب‌هوک
        webhook_data['chain'] = 'polygon'
        if 'currency' not in webhook_data:
            webhook_data['currency'] = 'matic'
            
        # فراخوانی پردازشگر اصلی
        return super().process_webhook(webhook_data)
    
    def update_transaction(self, blockchain, tx_hash):
        """
        به‌روزرسانی تراکنش پالیگان
        
        Args:
            blockchain (str): نام بلاکچین
            tx_hash (str): هش تراکنش
            
        Returns:
            dict: نتیجه به‌روزرسانی
        """
        logger.info(f"به‌روزرسانی تراکنش پالیگان: {tx_hash}")
        
        # فراخوانی متد اصلی
        return super().update_transaction(blockchain, tx_hash) 