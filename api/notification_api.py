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
    # معیار جدید: توکن باید حداقل 20 کاراکتر باشد و اکثراً شامل حروف، اعداد، خط تیره، دونقطه و نشانه‌های دیگر باشد
    # FCM توکن‌ها می‌توانند طول متغیر داشته باشند و شامل کاراکترهای مختلف باشند
    if not token or not isinstance(token, str):
        logger.warning(f"توکن نامعتبر: {token} - نوع: {type(token)}")
        return False
        
    # حداقل طول توکن FCM معتبر
    if len(token) < 20:
        logger.warning(f"توکن خیلی کوتاه است: {len(token)} کاراکتر")
        return False
        
    # بررسی اینکه توکن فقط شامل کاراکترهای مجاز است
    pattern = r'^[a-zA-Z0-9:_\-]+$'
    result = bool(re.match(pattern, token))
    if not result:
        logger.warning(f"توکن دارای کاراکترهای غیرمجاز است: {token}")
    return result

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
    try:
        logger.info("درخواست ثبت دستگاه جدید دریافت شد")
        
        data = request.get_json()
        if not data:
            logger.warning("داده‌های JSON دریافت نشد")
            raise ValidationError("داده‌های ورودی نامعتبر")
        
        # اعتبارسنجی داده‌ها با ثبت لاگ برای عیب‌یابی
        user_id = data.get('UserID')
        if not user_id:
            logger.warning("شناسه کاربر در درخواست وجود ندارد")
            raise ValidationError("شناسه کاربر الزامی است")
        else:
            logger.info(f"درخواست برای کاربر: {user_id}")
        
        wallet_id = data.get('WalletID')
        if not wallet_id:
            logger.warning("شناسه کیف پول در درخواست وجود ندارد")
            raise ValidationError("شناسه کیف پول الزامی است")
        else:
            logger.info(f"درخواست برای کیف پول: {wallet_id}")
        
        device_token = data.get('DeviceToken')
        if not device_token:
            logger.warning("توکن دستگاه در درخواست وجود ندارد")
            raise ValidationError("توکن دستگاه الزامی است")
        else:
            logger.info(f"طول توکن دستگاه: {len(device_token)} کاراکتر")
        
        device_name = data.get('DeviceName', 'Unknown Device')
        device_type = data.get('DeviceType', 'unknown')
        
        logger.info(f"دستگاه: {device_name}, نوع: {device_type}")
        
        # اعتبارسنجی فرمت توکن با سطح سختگیری کمتر
        if not device_token or not isinstance(device_token, str) or len(device_token) < 10:
            logger.warning(f"توکن دستگاه نامعتبر است: {device_token}")
            raise ValidationError("فرمت توکن دستگاه نامعتبر است")
        
        session = SessionLocal()
        try:
            # بررسی وجود کاربر
            user = session.query(Users).filter(Users.UserID == user_id).first()
            if not user:
                logger.warning(f"کاربر با شناسه {user_id} یافت نشد")
                raise ValidationError(f"کاربر با شناسه {user_id} یافت نشد")
            
            # بررسی وجود کیف پول
            wallet = session.query(Wallets).filter(
                Wallets.WalletID == wallet_id,
                Wallets.UserID == user_id
            ).first()
            if not wallet:
                logger.warning(f"کیف پول با شناسه {wallet_id} برای کاربر {user_id} یافت نشد")
                raise ValidationError(f"کیف پول با شناسه {wallet_id} برای کاربر {user_id} یافت نشد")
            
            # بررسی وجود توکن دستگاه
            existing_device = session.query(UserDevices).filter(
                UserDevices.DeviceToken == device_token
            ).first()
            
            if existing_device:
                # به‌روزرسانی رکورد موجود
                try:
                    existing_device.UserID = user_id
                    existing_device.WalletID = wallet_id
                    if device_name:
                        existing_device.DeviceName = device_name
                    if device_type:
                        existing_device.DeviceType = device_type
                    existing_device.UpdatedAt = datetime.now()
                    
                    session.commit()
                    logger.info(f"توکن دستگاه موجود به‌روزرسانی شد برای کاربر {user_id} و کیف پول {wallet_id}")
                    
                    return jsonify({
                        "success": True,
                        "message": "توکن دستگاه با موفقیت به‌روزرسانی شد"
                    })
                except Exception as update_ex:
                    session.rollback()
                    logger.error(f"خطا در به‌روزرسانی دستگاه موجود: {str(update_ex)}", exc_info=True)
                    raise
            else:
                # ایجاد رکورد جدید
                try:
                    new_device = UserDevices(
                        UserID=user_id,
                        WalletID=wallet_id,
                        DeviceToken=device_token,
                        DeviceName=device_name,
                        DeviceType=device_type,
                        CreatedAt=datetime.now(),
                        UpdatedAt=datetime.now()
                    )
                    
                    session.add(new_device)
                    session.flush()  # برای اطمینان از اختصاص DeviceID قبل از commit
                    device_id = new_device.DeviceID
                    session.commit()
                    
                    logger.info(f"توکن دستگاه جدید با شناسه {device_id} ثبت شد برای کاربر {user_id} و کیف پول {wallet_id}")
                    
                    return jsonify({
                        "success": True,
                        "message": "توکن دستگاه با موفقیت ثبت شد",
                        "device_id": device_id
                    })
                except Exception as insert_ex:
                    session.rollback()
                    logger.error(f"خطا در ایجاد دستگاه جدید: {str(insert_ex)}", exc_info=True)
                    raise
                
        except IntegrityError as e:
            session.rollback()
            logger.error(f"خطای یکپارچگی دیتابیس: {str(e)}")
            return jsonify({
                "success": False,
                "message": "خطا در ثبت توکن دستگاه: توکن تکراری یا داده‌های نامعتبر"
            }), 400
            
        except ValidationError as e:
            logger.warning(f"خطای اعتبارسنجی: {str(e)}")
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
            
    except Exception as outer_ex:
        logger.critical(f"خطای نامشخص در ثبت دستگاه: {str(outer_ex)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"خطای سرور ناشناخته: {str(outer_ex)}"
        }), 500

@notification_api.route('/notifications/simple-register-device', methods=['POST'])
@handle_api_errors
def simple_register_device():
    """
    API ساده ثبت توکن دستگاه - برای شرایط خطا
    
    این API یک نسخه ساده‌تر از register-device است که حداقل کد را استفاده می‌کند
    تا مشکلات احتمالی در API اصلی را حذف کند.
    """
    try:
        logger.info("درخواست ساده ثبت دستگاه دریافت شد")
        
        # دریافت داده‌های درخواست
        data = request.get_json()
        logger.info(f"داده‌های دریافتی: {data}")
        
        # بررسی وجود فیلدهای ضروری
        user_id = data.get('UserID')
        wallet_id = data.get('WalletID')
        device_token = data.get('DeviceToken')
        
        if not user_id or not wallet_id or not device_token:
            logger.warning(f"فیلدهای اجباری وجود ندارند: UserID={user_id}, WalletID={wallet_id}, DeviceToken={device_token}")
            return jsonify({
                "success": False,
                "message": "فیلدهای UserID، WalletID و DeviceToken اجباری هستند"
            }), 400
        
        # دریافت فیلدهای اختیاری
        device_name = data.get('DeviceName', 'Unknown')
        device_type = data.get('DeviceType', 'unknown')
        
        # گزارش اطلاعات دستگاه برای عیب‌یابی
        logger.info(f"اطلاعات دستگاه: UserID={user_id}, WalletID={wallet_id}, Token length={len(device_token)}, DeviceName={device_name}, DeviceType={device_type}")
        
        # ایجاد اتصال به دیتابیس
        session = SessionLocal()
        
        try:
            # بررسی وجود توکن مشابه
            existing = session.query(UserDevices).filter(
                UserDevices.DeviceToken == device_token
            ).first()
            
            if existing:
                logger.info(f"توکن دستگاه موجود یافت شد: DeviceID={existing.DeviceID}")
                # به‌روزرسانی رکورد موجود
                existing.UserID = user_id
                existing.WalletID = wallet_id
                existing.DeviceName = device_name
                existing.DeviceType = device_type
                existing.UpdatedAt = datetime.now()
                
                session.commit()
                logger.info(f"رکورد دستگاه به‌روزرسانی شد: DeviceID={existing.DeviceID}")
                
                return jsonify({
                    "success": True,
                    "message": "توکن دستگاه با موفقیت به‌روزرسانی شد",
                    "device_id": existing.DeviceID
                })
            else:
                logger.info("ایجاد رکورد جدید دستگاه")
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
                logger.info(f"رکورد جدید دستگاه ایجاد شد: DeviceID={new_device.DeviceID}")
                
                return jsonify({
                    "success": True,
                    "message": "توکن دستگاه با موفقیت ثبت شد",
                    "device_id": new_device.DeviceID
                })
                
        except Exception as db_error:
            session.rollback()
            logger.error(f"خطای دیتابیس: {str(db_error)}", exc_info=True)
            return jsonify({
                "success": False,
                "message": f"خطا در عملیات دیتابیس: {str(db_error)}"
            }), 500
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"خطای نامشخص: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": f"خطای ناشناخته: {str(e)}"
        }), 500

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