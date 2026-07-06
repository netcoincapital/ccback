"""
FCM Push Service for Block Scanner
=====================================
زمانی که Block Scanner یک تراکنش جدید برای یک آدرس فعال کشف می‌کند،
این ماژول کارهای زیر را انجام می‌دهد:

1. یافتن WalletID از روی PublicAddress (جدول Address)
2. یافتن DeviceToken از روی WalletID (جدول UserDevices)
3. ارسال FCM Push Notification

این ماژول به صورت Lazy-loaded عمل می‌کند تا وابستگی به دیتابیس
در زمان import نداشته باشد.
"""

import time
import logging
from typing import Optional, Dict, Any, List
from decimal import Decimal

from utils.logging_config import get_logger

logger = get_logger(__file__)

# Lazy-loaded modules (to avoid circular imports and heavy startup)
_db_session = None
_send_notification_fn = None
_Address_model = None
_UserDevices_model = None
_Blockchains_model = None


def _lazy_init():
    """بارگذاری ماژول‌های سنگین فقط در صورت نیاز."""
    global _db_session, _send_notification_fn, _Address_model, _UserDevices_model, _Blockchains_model

    if _db_session is not None:
        return True

    try:
        from database import SessionLocal, Address, UserDevices, Blockchains
        from config.firebase import send_notification

        _db_session = SessionLocal
        _Address_model = Address
        _UserDevices_model = UserDevices
        _Blockchains_model = Blockchains
        _send_notification_fn = send_notification
        logger.debug("FCM Push: modules loaded lazily")
        return True
    except Exception as e:
        logger.error(f"FCM Push: lazy init failed: {e}")
        return False


# Mapping: chain name from block_scanner → BlockchainName in DB
CHAIN_NAME_MAP: Dict[str, str] = {
    "Ethereum": "Ethereum",
    "BSC": "BNB Smart Chain",
    "BNB Smart Chain": "BNB Smart Chain",
    "Polygon": "Polygon",
    "Avalanche": "Avalanche",
    "Arbitrum": "Arbitrum",
    "Optimism": "Optimism",
    "Tron": "Tron",
    "Solana": "Solana",
    "Bitcoin": "Bitcoin",
}

# Mapping: chain name → native token symbol
CHAIN_NATIVE_SYMBOL: Dict[str, str] = {
    "Ethereum": "ETH",
    "BSC": "BNB",
    "BNB Smart Chain": "BNB",
    "Polygon": "MATIC",
    "Avalanche": "AVAX",
    "Arbitrum": "ETH",
    "Optimism": "ETH",
    "Tron": "TRX",
    "Solana": "SOL",
    "Bitcoin": "BTC",
}

# Mapping: chain name → native token decimals for conversion
CHAIN_DECIMALS: Dict[str, int] = {
    "Ethereum": 18,
    "BSC": 18,
    "BNB Smart Chain": 18,
    "Polygon": 18,
    "Avalanche": 18,
    "Arbitrum": 18,
    "Optimism": 18,
    "Tron": 6,       # SUN → TRX (1 TRX = 10^6 SUN)
    "Solana": 9,      # Lamports → SOL (1 SOL = 10^9 Lamports)
    "Bitcoin": 8,     # Satoshis → BTC (1 BTC = 10^8 Satoshis)
}


def _find_wallet_by_address(public_address: str) -> Optional[Dict[str, Any]]:
    """
    پیدا کردن WalletID و AddressID از روی public address.
    
    Args:
        public_address: آدرس بلاکچین (مثلاً 0xabc...)
        
    Returns:
        dict包含 AddressID, WalletID, PublicAddress یا None
    """
    if not _lazy_init():
        return None

    try:
        session = _db_session()
        try:
            addr = session.query(_Address_model).filter(
                _Address_model.PublicAddress == public_address.lower()
            ).first()
            if addr:
                return {
                    "address_id": addr.AddressID,
                    "wallet_id": addr.WalletID,
                    "public_address": addr.PublicAddress,
                }
            return None
        finally:
            session.close()
    except Exception as e:
        logger.error(f"FCM Push: error finding wallet for {public_address}: {e}")
        return None


def _get_device_tokens(wallet_id: str) -> List[str]:
    """
    دریافت توکن‌های دستگاه برای یک کیف پول.
    
    Args:
        wallet_id: شناسه کیف پول
        
    Returns:
        لیست توکن‌های FCM دستگاه‌ها
    """
    if not _lazy_init():
        return []

    try:
        session = _db_session()
        try:
            devices = session.query(_UserDevices_model).filter(
                _UserDevices_model.WalletID == wallet_id
            ).all()
            return [d.DeviceToken for d in devices if d.DeviceToken]
        finally:
            session.close()
    except Exception as e:
        logger.error(f"FCM Push: error getting device tokens for {wallet_id}: {e}")
        return []


def _format_amount(raw_value: Any, chain_key: str, value_field: str) -> str:
    """
    تبدیل مقدار خام بلاکچین به عدد قابل خواندن.
    
    Args:
        raw_value: مقدار خام (مثلاً wei, sun, satoshi)
        chain_key: نام بلاکچین (برای تشخیص decimals)
        value_field: نام فیلد (value_wei, value_sun, value_sat, value_lamports)
        
    Returns:
        مقدار فرمت شده به صورت رشته (مثلاً "1.5")
    """
    try:
        value = int(raw_value) if raw_value else 0
        if value == 0:
            return "0"

        decimals = CHAIN_DECIMALS.get(chain_key, 18)
        amount = Decimal(value) / Decimal(10 ** decimals)
        
        # حذف صفرهای اضافی
        formatted = f"{amount:.{decimals}f}"
        if "." in formatted:
            formatted = formatted.rstrip("0").rstrip(".")
        return formatted
    except (ValueError, TypeError):
        return str(raw_value)


def _send_push_for_address(
    public_address: str,
    tx_data: Dict[str, Any],
    direction: str,
) -> bool:
    """
    ارسال پوش نوتیفیکیشن برای یک آدرس خاص.
    
    Args:
        public_address: آدرس بلاکچین
        tx_data: داده‌های تراکنش از block_scanner
        direction: "inbound" یا "outbound"
        
    Returns:
        bool: موفقیت
    """
    # 1. پیدا کردن Wallet
    wallet_info = _find_wallet_by_address(public_address)
    if not wallet_info:
        logger.debug(f"FCM Push: no wallet found for {public_address}")
        return False

    wallet_id = wallet_info["wallet_id"]

    # 2. پیدا کردن Device Tokens
    tokens = _get_device_tokens(wallet_id)
    if not tokens:
        logger.debug(f"FCM Push: no device tokens for wallet {wallet_id}")
        return False

    # 3. آماده‌سازی مقادیر
    chain_name = tx_data.get("blockchain", "Unknown")
    chain_key = chain_name
    # mapping chain_name to DB name for symbol lookup
    db_chain_name = CHAIN_NAME_MAP.get(chain_name, chain_name)
    token_symbol = CHAIN_NATIVE_SYMBOL.get(chain_name, chain_name.upper())

    # تشخیص فیلد مقدار
    value_field = "value_wei"
    if "value_sun" in tx_data:
        value_field = "value_sun"
    elif "value_sat" in tx_data:
        value_field = "value_sat"
    elif "value_lamports" in tx_data:
        value_field = "value_lamports"

    amount_str = _format_amount(tx_data.get(value_field, 0), chain_key, value_field)

    tx_hash = tx_data.get("hash", "")
    from_addr = tx_data.get("from", "")
    to_addr = tx_data.get("to", "")

    def _shorten(addr: str) -> str:
        if not addr or len(addr) < 10:
            return addr or ""
        return f"{addr[:6]}...{addr[-4:]}"

    # 4. ساختن عنوان و متن
    if direction == "outbound":
        title = f"💸 Sent: {amount_str} {token_symbol}"
        body = f"To {_shorten(to_addr)}"
        notification_type = "send"
    else:
        title = f"💰 Received: {amount_str} {token_symbol}"
        body = f"From {_shorten(from_addr)}"
        notification_type = "receive"

    # 5. ارسال به همه دستگاه‌ها
    if not _lazy_init():
        return False

    success_count = 0
    for token in tokens:
        try:
            result = _send_notification_fn(
                token=token,
                title=title,
                body=body,
                data={
                    "type": notification_type,
                    "direction": direction,
                    "amount": amount_str,
                    "symbol": token_symbol,
                    "currency": token_symbol,
                    "tx_hash": tx_hash,
                    "from_address": from_addr,
                    "to_address": to_addr,
                    "wallet_id": wallet_id,
                    "blockchain": chain_name,
                },
                priority="high",
            )
            if result:
                success_count += 1
        except Exception as e:
            logger.error(f"FCM Push: error sending to device: {e}")

    if success_count > 0:
        logger.info(
            f"FCM Push: sent {notification_type} notification for {tx_hash[:16]}... "
            f"to {success_count}/{len(tokens)} devices (wallet={wallet_id[:8]}...)"
        )
    return success_count > 0


def notify_new_transaction(tx_data: Dict[str, Any]) -> None:
    """
    نقطه ورود اصلی: بعد از کش کردن تراکنش در block_scanner صدا زده می‌شود.
    
    این تابع بررسی می‌کند که آیا آدرس‌های in/out در دیتابیس وجود دارند
    و برایشان پوش نوتیفیکیشن می‌فرستد.
    
    Args:
        tx_data: دیکشنری تراکنش از block_scanner
                 شامل hash, blockchain, block_number, from, to,
                 value_wei/value_sun/value_sat/value_lamports, timestamp
    """
    try:
        tx_to = tx_data.get("to", "").lower().strip()
        tx_from = tx_data.get("from", "").lower().strip()

        # Inbound: آدرس مقصد (to) آدرس کاربر ماست
        if tx_to and tx_to != "0x":
            _send_push_for_address(tx_to, tx_data, "inbound")
        else:
            # برای بیت‌کوین to خالی است، پس direction رو برعکس تشخیص بده
            if tx_from:
                _send_push_for_address(tx_from, tx_data, "outbound")

        # Outbound: آدرس مبدأ (from) آدرس کاربر ماست
        if tx_from and tx_from != "0x" and tx_from != tx_to:
            _send_push_for_address(tx_from, tx_data, "outbound")

    except Exception as e:
        logger.error(f"FCM Push: notify_new_transaction error: {e}", exc_info=True)
