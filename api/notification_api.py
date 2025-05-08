import logging
from flask import Blueprint, request, jsonify
from utils.logging_config import get_logger
from database import SessionLocal, UserDevices, Users, Wallets
from sqlalchemy.exc import IntegrityError
from schemas.notification_schemas import DeviceRegistrationRequest
from security.validators import SecurityUtils
from utils.error_handlers import APIErrorHandler, handle_api_errors
from security.validators import ValidationError
from config.firebase import send_notification
import re
from datetime import datetime

# تنظیم لاگر
logger = get_logger(__file__)

# ایجاد Blueprint
notification_api = Blueprint('notification_api', __name__)

def validate_fcm_token(token):
    """
    اعتبارسنجی فرمت توکن FCM
    """
    # الگوی توکن FCM: معمولاً با 'f' شروع می‌شود و شامل حروف، اعداد و کاراکترهای خاص است
    pattern = r'^[a-zA-Z0-9_-]{152,}$'
    return bool(re.match(pattern, token))

@notification_api.route('/notifications/register-device', methods=['POST'])
@SecurityUtils.rate_limit(requests=5, window=300)
@handle_api_errors
def register_device():
    """
    ثبت توکن دستگاه برای دریافت اعلان‌های پوش
    
    این API توکن دستگاه را برای یک کاربر و کیف پول خاص ثبت می‌کند
    تا بتواند اعلان‌های تراکنش‌های جدید را دریافت کند.
    
    ---
    tags:
      - Notifications
    summary: ثبت توکن دستگاه برای اعلان‌های پوش
    description: توکن دستگاه را برای دریافت اعلان‌های پوش ثبت می‌کند
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/DeviceRegistrationRequest'
    responses:
      '200':
        description: توکن دستگاه با موفقیت ثبت شد
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/DeviceRegistrationResponse'
      '400':
        description: پارامترهای نامعتبر
      '404':
        description: کاربر یا کیف پول یافت نشد
      '500':
        description: خطای سرور
    """
    data = request.get_json()
    if not data:
        raise ValidationError("داده‌های ورودی نامعتبر")
    
    # اعتبارسنجی داده‌ها
    user_id = data.get('UserID')
    if not user_id:
        raise ValidationError("شناسه کاربر الزامی است")
    
    wallet_id = data.get('WalletID')
    if not wallet_id:
        raise ValidationError("شناسه کیف پول الزامی است")
    
    device_token = data.get('DeviceToken')
    if not device_token:
        raise ValidationError("توکن دستگاه الزامی است")
    
    # اعتبارسنجی فرمت توکن
    if not validate_fcm_token(device_token):
        raise ValidationError("فرمت توکن دستگاه نامعتبر است")
    
    device_name = data.get('DeviceName')
    device_type = data.get('DeviceType')
    
    session = SessionLocal()
    try:
        # بررسی وجود کاربر
        user = session.query(Users).filter(Users.UserID == user_id).first()
        if not user:
            raise ValidationError(f"کاربر با شناسه {user_id} یافت نشد")
        
        # بررسی وجود کیف پول
        wallet = session.query(Wallets).filter(
            Wallets.WalletID == wallet_id,
            Wallets.UserID == user_id
        ).first()
        if not wallet:
            raise ValidationError(f"کیف پول با شناسه {wallet_id} برای کاربر {user_id} یافت نشد")
        
        # بررسی وجود توکن دستگاه
        existing_device = session.query(UserDevices).filter(
            UserDevices.DeviceToken == device_token
        ).first()
        
        if existing_device:
            # به‌روزرسانی رکورد موجود
            existing_device.UserID = user_id
            existing_device.WalletID = wallet_id
            if device_name:
                existing_device.DeviceName = device_name
            if device_type:
                existing_device.DeviceType = device_type
            
            logger.info(f"توکن دستگاه موجود به‌روزرسانی شد برای کاربر {user_id} و کیف پول {wallet_id}")
            
            session.commit()
            return jsonify({
                "success": True,
                "message": "توکن دستگاه با موفقیت به‌روزرسانی شد"
            })
        else:
            # ایجاد رکورد جدید
            new_device = UserDevices(
                UserID=user_id,
                WalletID=wallet_id,
                DeviceToken=device_token,
                DeviceName=device_name,
                DeviceType=device_type
            )
            
            session.add(new_device)
            session.commit()
            
            logger.info(f"توکن دستگاه جدید ثبت شد برای کاربر {user_id} و کیف پول {wallet_id}")
            
            return jsonify({
                "success": True,
                "message": "توکن دستگاه با موفقیت ثبت شد"
            })
            
    except IntegrityError as e:
        session.rollback()
        logger.error(f"خطای یکپارچگی دیتابیس: {str(e)}")
        return jsonify({
            "success": False,
            "message": "خطا در ثبت توکن دستگاه: توکن تکراری یا داده‌های نامعتبر"
        }), 400
        
    except ValidationError as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400
        
    except Exception as e:
        session.rollback()
        logger.error(f"خطا در ثبت توکن دستگاه: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"خطای سرور: {str(e)}"
        }), 500
        
    finally:
        session.close()

@notification_api.route('/notifications/test', methods=['POST'])
@SecurityUtils.rate_limit(requests=3, window=300)
@handle_api_errors
def test_notification():
    """
    ارسال اعلان تست به دستگاه
    
    این API برای تست عملکرد اعلان‌ها استفاده می‌شود.
    """
    data = request.get_json()
    if not data:
        raise ValidationError("داده‌های ورودی نامعتبر")
    
    device_token = data.get('DeviceToken')
    if not device_token:
        raise ValidationError("توکن دستگاه الزامی است")
    
    # اعتبارسنجی فرمت توکن
    if not validate_fcm_token(device_token):
        raise ValidationError("فرمت توکن دستگاه نامعتبر است")
    
    try:
        # ارسال اعلان تست
        success = send_notification(
            token=device_token,
            title="تست اعلان",
            body="این یک اعلان تست است",
            data={"type": "test", "timestamp": str(datetime.utcnow())},
            priority="high"
        )
        
        if success:
            return jsonify({
                "success": True,
                "message": "اعلان تست با موفقیت ارسال شد"
            })
        else:
            return jsonify({
                "success": False,
                "message": "خطا در ارسال اعلان تست"
            }), 500
            
    except Exception as e:
        logger.error(f"خطا در ارسال اعلان تست: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"خطای سرور: {str(e)}"
        }), 500

@notification_api.route('/notifications/test-notify', methods=['POST'])
@SecurityUtils.rate_limit(requests=3, window=300)
@handle_api_errors
def test_notify():
    """
    ارسال اعلان تست به دستگاه
    
    این API برای تست مستقیم متد notify بدون وابستگی به تراکنش واقعی استفاده می‌شود.
    """
    data = request.get_json()
    if not data:
        raise ValidationError("داده‌های ورودی نامعتبر")
    
    wallet_id = data.get('wallet_id')
    if not wallet_id:
        raise ValidationError("شناسه کیف پول الزامی است")
    
    tx_id = data.get('tx_id')
    if not tx_id:
        raise ValidationError("شناسه تراکنش الزامی است")
    
    try:
        # آماده‌سازی داده‌های تست
        webhook_data = {
            'timestamp': str(datetime.utcnow()),
            'chain': 'TEST'
        }
        
        relevant_addresses = [{
            'wallet_id': wallet_id
        }]
        
        # ارسال اعلان تست
        from webhook.notification_service import NotificationService
        notification_service = NotificationService()
        success = notification_service.notify(
            transaction_type='address_transaction',
            transaction_id=tx_id,
            relevant_addresses=relevant_addresses,
            webhook_data=webhook_data
        )
        
        if success:
            return jsonify({
                "success": True,
                "message": "اعلان تست با موفقیت ارسال شد"
            })
        else:
            return jsonify({
                "success": False,
                "message": "خطا در ارسال اعلان تست"
            }), 500
            
    except Exception as e:
        logger.error(f"خطا در ارسال اعلان تست: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"خطای سرور: {str(e)}"
        }), 500 