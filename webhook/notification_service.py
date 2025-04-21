import logging
import json
import requests
from utils.logging_config import get_logger

# تنظیم لاگر
logger = get_logger(__file__)

class NotificationService:
    """
    کلاس سرویس اعلان‌ها برای ارسال اطلاعات به فرانت‌اند و اعلان‌های پوش
    """
    
    def __init__(self):
        """
        مقداردهی اولیه کلاس سرویس اعلان‌ها
        """
        # تنظیمات پیکربندی سرویس اعلان را می‌توان اینجا اضافه کرد
        pass
    
    def notify(self, transaction_type, transaction_id, relevant_addresses, webhook_data):
        """
        ارسال اعلان به فرانت‌اند و کاربران در مورد تراکنش جدید
        
        Args:
            transaction_type (str): نوع تراکنش ('contract_event' یا 'address_transaction')
            transaction_id (str): شناسه تراکنش
            relevant_addresses (list): لیست اطلاعات آدرس‌های مرتبط
            webhook_data (dict): داده‌های کامل وب‌هوک
            
        Returns:
            bool: نتیجه عملیات
        """
        try:
            logger.info(f"ارسال اعلان برای تراکنش {transaction_id}")
            
            # استخراج شناسه‌های کیف پول و کاربران (با فرض اینکه در دسترس هستند)
            wallet_ids = list(set([address_info['wallet_id'] for address_info in relevant_addresses]))
            
            # آماده‌سازی داده‌های اعلان
            notification_data = {
                'type': 'new_transaction',
                'transaction_type': transaction_type,
                'transaction_id': transaction_id,
                'affected_wallets': wallet_ids,
                'timestamp': webhook_data.get('timestamp'),
                'blockchain': webhook_data.get('chain')
            }
            
            logger.debug(f"داده‌های اعلان: {notification_data}")
            
            # ارسال اعلان از طریق WebSocket یا API به فرانت‌اند
            self._send_to_frontend(notification_data)
            
            # ارسال اعلان‌های پوش به دستگاه‌های کاربران
            self._send_push_notifications(wallet_ids, transaction_id, transaction_type)
            
            return True
            
        except Exception as e:
            logger.error(f"خطا در ارسال اعلان‌ها: {str(e)}", exc_info=True)
            return False
    
    def _send_to_frontend(self, data):
        """
        ارسال داده به فرانت‌اند از طریق WebSocket یا API
        
        Args:
            data (dict): داده‌هایی که باید ارسال شوند
            
        Returns:
            bool: نتیجه عملیات
        """
        try:
            # در پیاده‌سازی واقعی، این بخش باید با سیستم ارتباطی مانند WebSocket یا REST API کار کند
            logger.info("ارسال اعلان به فرانت‌اند")
            logger.debug(f"داده‌های ارسالی: {data}")
            
            # برای این نمونه، فقط پیام‌های لاگ ثبت می‌کنیم
            # در پیاده‌سازی واقعی، ارسال داده‌ها به سرور WebSocket یا فراخوانی یک API وب اینجا انجام می‌شود
            
            # نمونه کد برای ارسال به یک API REST:
            # response = requests.post(
            #     "https://api.example.com/notifications",
            #     json=data,
            #     headers={"Content-Type": "application/json"}
            # )
            # logger.debug(f"پاسخ API: {response.status_code} - {response.text}")
            # return response.status_code == 200
            
            return True
            
        except Exception as e:
            logger.error(f"خطا در ارسال به فرانت‌اند: {str(e)}", exc_info=True)
            return False
    
    def _send_push_notifications(self, wallet_ids, transaction_id, transaction_type):
        """
        ارسال اعلان‌های پوش به دستگاه‌های کاربران
        
        Args:
            wallet_ids (list): لیست شناسه‌های کیف پول
            transaction_id (str): شناسه تراکنش
            transaction_type (str): نوع تراکنش
            
        Returns:
            bool: نتیجه عملیات
        """
        try:
            if not wallet_ids:
                logger.warning("هیچ شناسه کیف پولی برای ارسال اعلان پوش یافت نشد")
                return False
            
            logger.info(f"ارسال اعلان‌های پوش برای {len(wallet_ids)} کیف پول")
            
            # دریافت توکن‌های دستگاه برای کیف پول‌های مرتبط
            device_tokens = self._get_device_tokens_for_wallets(wallet_ids)
            
            if not device_tokens:
                logger.warning("هیچ توکن دستگاهی برای ارسال اعلان پوش یافت نشد")
                return False
            
            logger.info(f"ارسال اعلان‌های پوش به {len(device_tokens)} دستگاه")
            
            # آماده‌سازی پیام اعلان
            notification_message = self._create_notification_message(transaction_id, transaction_type)
            
            # ارسال اعلان‌ها به هر دستگاه
            for token in device_tokens:
                self._send_push_to_device(token, notification_message)
            
            return True
            
        except Exception as e:
            logger.error(f"خطا در ارسال اعلان‌های پوش: {str(e)}", exc_info=True)
            return False
    
    def _get_device_tokens_for_wallets(self, wallet_ids):
        """
        دریافت توکن‌های دستگاه برای کیف پول‌ها از دیتابیس
        
        Args:
            wallet_ids (list): لیست شناسه‌های کیف پول
            
        Returns:
            list: لیست توکن‌های دستگاه
        """
        # این تابع باید پیاده‌سازی شود تا توکن‌های دستگاه را از دیتابیس دریافت کند
        # برای این نمونه، فقط یک لیست خالی برمی‌گردانیم
        logger.debug(f"دریافت توکن‌های دستگاه برای کیف پول‌های {wallet_ids}")
        
        # نمونه کد برای دریافت توکن‌های دستگاه از دیتابیس:
        # from database import get_db_connection
        # tokens = []
        # with get_db_connection() as conn:
        #     cursor = conn.cursor()
        #     placeholders = ','.join(['%s'] * len(wallet_ids))
        #     cursor.execute(f"SELECT DeviceToken FROM UserDevices WHERE WalletID IN ({placeholders})", wallet_ids)
        #     tokens = [row[0] for row in cursor.fetchall()]
        # return tokens
        
        # برای این نمونه، فقط یک لیست خالی برمی‌گردانیم
        return []
    
    def _create_notification_message(self, transaction_id, transaction_type):
        """
        ایجاد پیام اعلان بر اساس نوع تراکنش
        
        Args:
            transaction_id (str): شناسه تراکنش
            transaction_type (str): نوع تراکنش
            
        Returns:
            dict: پیام اعلان
        """
        # تنظیم پیام بر اساس نوع تراکنش
        if transaction_type == 'contract_event':
            title = "تراکنش قرارداد جدید"
            body = f"یک رویداد قرارداد هوشمند در تراکنش {transaction_id[:8]}... شناسایی شد"
        else:
            title = "تراکنش جدید"
            body = f"یک تراکنش جدید با شناسه {transaction_id[:8]}... دریافت شد"
        
        return {
            "title": title,
            "body": body,
            "data": {
                "transaction_id": transaction_id,
                "type": transaction_type
            }
        }
    
    def _send_push_to_device(self, device_token, message):
        """
        ارسال اعلان پوش به یک دستگاه خاص با استفاده از FCM یا سرویس مشابه
        
        Args:
            device_token (str): توکن دستگاه
            message (dict): پیام اعلان
            
        Returns:
            bool: نتیجه عملیات
        """
        try:
            logger.debug(f"ارسال اعلان پوش به دستگاه {device_token}")
            
            # در پیاده‌سازی واقعی، این تابع باید با یک سرویس اعلان پوش مانند Firebase Cloud Messaging ارتباط برقرار کند
            # نمونه کد برای ارسال اعلان با FCM:
            # from firebase_admin import messaging
            # message = messaging.Message(
            #     notification=messaging.Notification(
            #         title=message["title"],
            #         body=message["body"],
            #     ),
            #     data=message["data"],
            #     token=device_token,
            # )
            # response = messaging.send(message)
            # logger.debug(f"پاسخ FCM: {response}")
            # return True
            
            # برای این نمونه، فقط موفقیت را برمی‌گردانیم
            return True
            
        except Exception as e:
            logger.error(f"خطا در ارسال اعلان پوش به دستگاه {device_token}: {str(e)}")
            return False 