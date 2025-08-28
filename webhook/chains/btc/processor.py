from CC.webhook.transaction_processor import TransactionProcessor
from CC.utils.logging_config import get_logger
from CC.webhook.chains.btc.utils import analyze_btc_inputs_outputs

logger = get_logger(__name__)

class BitcoinProcessor(TransactionProcessor):
    """پردازشگر وب‌هوک‌های مخصوص بیت‌کوین"""
    
    def __init__(self):
        super().__init__()
        logger.info("پردازشگر بیت‌کوین راه‌اندازی شد")
    
    def process_webhook(self, webhook_data):
        """
        پردازش وب‌هوک بیت‌کوین
        این متد می‌تواند منطق خاص بیت‌کوین را اجرا کند
        
        Args:
            webhook_data (dict): داده‌های وب‌هوک دریافتی
            
        Returns:
            dict: نتیجه پردازش
        """
        logger.info("پردازش وب‌هوک بیت‌کوین")
        
        # تحلیل ورودی‌ها و خروجی‌های تراکنش بیت‌کوین
        inputs = webhook_data.get('inputs', [])
        outputs = webhook_data.get('outputs', [])
        
        if inputs and outputs:
            analysis = analyze_btc_inputs_outputs(inputs, outputs)
            webhook_data['btc_analysis'] = analysis
            
            # محاسبه کارمزد تراکنش (مجموع ورودی‌ها - مجموع خروجی‌ها)
            total_input = sum(float(inp.get('value', 0)) for inp in inputs)
            total_output = sum(float(out.get('value', 0)) for out in outputs)
            fee = total_input - total_output
            
            # اگر کارمزد محاسبه شده منطقی باشد، آن را به داده‌های وب‌هوک اضافه می‌کنیم
            if fee > 0:
                webhook_data['fee'] = fee
                logger.info(f"کارمزد محاسبه شده برای تراکنش: {fee} BTC")
        
        # افزودن اطلاعات تکمیلی به داده‌های وب‌هوک
        webhook_data['chain'] = 'bitcoin'
        if 'currency' not in webhook_data:
            webhook_data['currency'] = 'btc'
            
        # فراخوانی پردازشگر اصلی
        return super().process_webhook(webhook_data)
    
    def update_transaction(self, blockchain, tx_hash):
        """
        به‌روزرسانی تراکنش بیت‌کوین
        
        Args:
            blockchain (str): نام بلاکچین
            tx_hash (str): هش تراکنش
            
        Returns:
            dict: نتیجه به‌روزرسانی
        """
        logger.info(f"به‌روزرسانی تراکنش بیت‌کوین: {tx_hash}")
        
        # فراخوانی متد اصلی
        return super().update_transaction(blockchain, tx_hash) 