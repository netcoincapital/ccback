"""
Shared notification helpers
============================
توابع مشترک برای همه ماژول‌های نوتیفیکیشن.

- پیدا کردن Device Tokenها برای یک User
- پیدا کردن Walletهای یک User
- ارسال نوتیفیکیشن
"""

from typing import List, Optional, Dict, Any
from utils.logging_config import get_logger

logger = get_logger(__file__)

# Lazy-loaded modules
_db_session = None
_send_notification_fn = None
_Wallets_model = None
_UserDevices_model = None
_Users_model = None


def _lazy_init():
    global _db_session, _send_notification_fn, _Wallets_model, _UserDevices_model, _Users_model
    if _db_session is not None:
        return True
    try:
        from database import SessionLocal, Wallets, UserDevices, Users
        from config.firebase import send_notification
        _db_session = SessionLocal
        _Wallets_model = Wallets
        _UserDevices_model = UserDevices
        _Users_model = Users
        _send_notification_fn = send_notification
        logger.debug("Notification base: modules loaded lazily")
        return True
    except Exception as e:
        logger.error(f"Notification base: lazy init failed: {e}")
        return False


def get_user_wallets(user_id: str) -> List[str]:
    """دریافت لیست WalletIDهای یک کاربر."""
    if not _lazy_init():
        return []
    try:
        session = _db_session()
        try:
            wallets = session.query(_Wallets_model).filter(
                _Wallets_model.UserID == user_id
            ).all()
            return [w.WalletID for w in wallets]
        finally:
            session.close()
    except Exception as e:
        logger.error(f"get_user_wallets error: {e}")
        return []


def get_all_user_ids() -> List[str]:
    """دریافت لیست همه UserIDها (برای broadcast)."""
    if not _lazy_init():
        return []
    try:
        session = _db_session()
        try:
            users = session.query(_Users_model.UserID).all()
            return [u.UserID for u in users]
        finally:
            session.close()
    except Exception as e:
        logger.error(f"get_all_users error: {e}")
        return []


def get_device_tokens(user_id: str) -> List[str]:
    """
    دریافت Device Tokenهای یک کاربر از همه Walletهایش.
    
    Args:
        user_id: شناسه کاربر
        
    Returns:
        لیست توکن‌های FCM
    """
    wallet_ids = get_user_wallets(user_id)
    if not wallet_ids:
        logger.debug(f"No wallets found for user {user_id[:8]}...")
        return []

    if not _lazy_init():
        return []

    try:
        session = _db_session()
        try:
            devices = session.query(_UserDevices_model).filter(
                _UserDevices_model.WalletID.in_(wallet_ids)
            ).all()
            tokens = list(set(d.DeviceToken for d in devices if d.DeviceToken))
            logger.debug(f"Found {len(tokens)} device tokens for user {user_id[:8]}...")
            return tokens
        finally:
            session.close()
    except Exception as e:
        logger.error(f"get_device_tokens error: {e}")
        return []


def get_device_tokens_for_wallets(wallet_ids: List[str]) -> List[str]:
    """دریافت Device Tokenها برای لیستی از Walletها."""
    if not _lazy_init():
        return []
    try:
        session = _db_session()
        try:
            devices = session.query(_UserDevices_model).filter(
                _UserDevices_model.WalletID.in_(wallet_ids)
            ).all()
            return list(set(d.DeviceToken for d in devices if d.DeviceToken))
        finally:
            session.close()
    except Exception as e:
        logger.error(f"get_device_tokens_for_wallets error: {e}")
        return []


def get_device_tokens_by_device_id(device_id: str) -> List[str]:
    """
    دریافت Device Tokenها به صورت مستقیم با DeviceID (بدون عبور از Wallets).
    
    این متد برای anonymous flow استفاده می‌شود که در آن
    DeviceID ناشناس در فیلد UserID جدول UserDevices ذخیره شده است.

    Args:
        device_id: شناسه ناشناس دستگاه (UUID v4)
        
    Returns:
        لیست توکن‌های FCM
    """
    if not _lazy_init():
        return []
    try:
        session = _db_session()
        try:
            devices = session.query(_UserDevices_model).filter(
                _UserDevices_model.UserID == device_id
            ).all()
            tokens = list(set(d.DeviceToken for d in devices if d.DeviceToken))
            if tokens:
                logger.debug(f"Found {len(tokens)} device tokens for device_id {device_id[:8]}...")
            return tokens
        finally:
            session.close()
    except Exception as e:
        logger.error(f"get_device_tokens_by_device_id error: {e}")
        return []


def _send_push_to_tokens(
    tokens: List[str],
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
    priority: str = "high",
) -> int:
    """ارسال پوش نوتیفیکیشن به لیستی از توکن‌ها (متد داخلی)."""
    if not tokens or not _lazy_init():
        return 0
    success_count = 0
    for token in tokens:
        try:
            result = _send_notification_fn(
                token=token,
                title=title,
                body=body,
                data=data or {},
                priority=priority,
            )
            if result:
                success_count += 1
        except Exception as e:
            logger.error(f"_send_push_to_tokens: error: {e}")
    return success_count


def send_push_to_user(
    user_id: str,
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
    priority: str = "high",
) -> int:
    """
    ارسال پوش نوتیفیکیشن به همه دستگاه‌های یک کاربر.
    
    استراتژی (دو مرحله‌ای):
      ۱. اول جستجوی مستقیم در UserDevices.UserID (حالت anonymous)
      ۲. اگر پیدا نشد، جستجوی کلاسیک از طریق Wallets (backward compatible)

    Args:
        user_id: شناسه کاربر یا DeviceID ناشناس
        title: عنوان نوتیفیکیشن
        body: متن نوتیفیکیشن
        data: دیتای اضافی (دیکشنری با مقادیر string)
        priority: "normal" یا "high"
        
    Returns:
        تعداد دستگاه‌هایی که نوتیفیکیشن با موفقیت براشون ارسال شد
    """
    # Phase 1: Direct lookup (anonymous DeviceID mode — Wallets.UserID lookup)
    tokens = get_device_tokens_by_device_id(user_id)
    if tokens:
        count = _send_push_to_tokens(tokens, title, body, data, priority)
        logger.info(
            f"Notification: '{title}' sent to {count}/{len(tokens)} devices "
            f"(anonymous mode) for {user_id[:8]}..."
        )
        return count

    # Phase 2: Legacy lookup via Wallets (backward compatible with real UserIDs)
    tokens = get_device_tokens(user_id)
    if not tokens:
        logger.debug(f"send_push_to_user: no tokens for user {user_id[:8]}...")
        return 0

    count = _send_push_to_tokens(tokens, title, body, data, priority)
    logger.info(
        f"Notification: '{title}' sent to {count}/{len(tokens)} devices "
        f"for user {user_id[:8]}..."
    )
    return count


def send_push_to_all_users(
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
    priority: str = "high",
) -> int:
    """
    ارسال Broadcast به همه کاربران (برای اولویت ۵).
    
    Args:
        title: عنوان
        body: متن
        data: دیتای اضافی
        
    Returns:
        تعداد کل Deviceهایی که نوتیفیکیشن دریافت کردند
    """
    user_ids = get_all_user_ids()
    total = 0
    for uid in user_ids:
        total += send_push_to_user(uid, title, body, data, priority)
    logger.info(f"Broadcast: '{title}' sent to {total} devices across {len(user_ids)} users")
    return total
