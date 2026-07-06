"""
Priority 3 — Market & Price Notifications
============================================
نوتیفیکیشن‌های بازار و قیمت:
- هشدار قیمت (Price Alerts)
- نوسانات شدید (Volatility Alerts)
- گزارش دوره‌ای پورتفوی (Portfolio Summary)

معماری:
- PriceAlertNotifier: سرویس اصلی برای ارسال نوتیفیکیشن
- PriceAlertScheduler: بررسی دوره‌ای قیمت‌ها و ارسال هشدار
- Alert Subscriptions در دیتابیس (جدول settings)
"""

import json
import time
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta

from utils.logging_config import get_logger
from .base import send_push_to_user, get_user_wallets, get_device_tokens

logger = get_logger(__file__)

# Lazy DB session
_db_session = None
_UserHolding_model = None
_Transfers_model = None
_Wallets_model = None


def _lazy_init():
    global _db_session, _UserHolding_model, _Transfers_model, _Wallets_model
    if _db_session is not None:
        return True
    try:
        from database import SessionLocal, UserHolding, Transfers, Wallets
        _db_session = SessionLocal
        _UserHolding_model = UserHolding
        _Transfers_model = Transfers
        _Wallets_model = Wallets
        return True
    except Exception as e:
        logger.error(f"PriceAlerts: lazy init failed: {e}")
        return False


class PriceAlertNotifier:
    """ارسال هشدارهای قیمتی به کاربر."""

    @staticmethod
    def notify_price_alert(
        user_id: str,
        symbol: str,
        current_price: float,
        target_price: float,
        alert_type: str,  # above / below
    ) -> bool:
        """
        ارسال نوتیفیکیشن هنگام رسیدن قیمت به مقدار هدف.
        
        Args:
            user_id: شناسه کاربر
            symbol: نماد ارز (مثلاً BTC)
            current_price: قیمت فعلی
            target_price: قیمت هدف
            alert_type: "above" یعنی قیمت بالاتر رفت, "below" یعنی پایین‌تر آمد
            
        Returns:
            bool: موفقیت
        """
        if alert_type == "above":
            title = f"📈 {symbol} Hit Your Target!"
            body = f"{symbol} is now ${current_price:,.2f} (target: ${target_price:,.2f})"
        else:
            title = f"📉 {symbol} Dropped to Your Alert"
            body = f"{symbol} is now ${current_price:,.2f} (target: ${target_price:,.2f})"

        count = send_push_to_user(
            user_id=user_id,
            title=title,
            body=body,
            data={
                "type": "price_alert",
                "symbol": symbol,
                "current_price": str(current_price),
                "target_price": str(target_price),
                "alert_type": alert_type,
            },
            priority="normal",
        )
        return count > 0

    @staticmethod
    def notify_volatility(
        user_id: str,
        symbol: str,
        change_percent: float,
        current_price: float,
        direction: str,  # up / down
    ) -> bool:
        """
        ارسال نوتیفیکیشن هنگام نوسان شدید بازار.
        
        Args:
            user_id: شناسه کاربر
            symbol: نماد ارز
            change_percent: درصد تغییر
            current_price: قیمت فعلی
            direction: "up" یا "down"
            
        Returns:
            bool: موفقیت
        """
        if direction == "up":
            title = f"🚀 {symbol} Surged {abs(change_percent):.1f}%"
        else:
            title = f"💥 {symbol} Dropped {abs(change_percent):.1f}%"
        
        body = f"{symbol} is at ${current_price:,.2f}"

        count = send_push_to_user(
            user_id=user_id,
            title=title,
            body=body,
            data={
                "type": "volatility_alert",
                "symbol": symbol,
                "change_percent": str(change_percent),
                "current_price": str(current_price),
                "direction": direction,
            },
            priority="normal",
        )
        return count > 0

    @staticmethod
    def notify_portfolio_summary(
        user_id: str,
        total_balance_usd: float,
        change_24h_percent: float,
        change_7d_percent: float,
        top_holding: Optional[str] = None,
    ) -> bool:
        """
        ارسال گزارش دوره‌ای پورتفوی.
        
        Args:
            user_id: شناسه کاربر
            total_balance_usd: موجودی کل به USD
            change_24h_percent: تغییر ۲۴ ساعت
            change_7d_percent: تغییر ۷ روز
            top_holding: بزرگترین دارایی (اختیاری)
            
        Returns:
            bool: موفقیت
        """
        emoji = "📈" if change_24h_percent >= 0 else "📉"
        
        title = f"{emoji} Portfolio Summary"
        
        body_parts = [f"Balance: ${total_balance_usd:,.2f}"]
        
        if change_24h_percent >= 0:
            body_parts.append(f"24h: +{change_24h_percent:.1f}%")
        else:
            body_parts.append(f"24h: {change_24h_percent:.1f}%")
            
        if change_7d_percent >= 0:
            body_parts.append(f"7d: +{change_7d_percent:.1f}%")
        else:
            body_parts.append(f"7d: {change_7d_percent:.1f}%")
            
        if top_holding:
            body_parts.append(f"Top: {top_holding}")
        
        body = " · ".join(body_parts)

        count = send_push_to_user(
            user_id=user_id,
            title=title,
            body=body,
            data={
                "type": "portfolio_summary",
                "total_balance_usd": str(total_balance_usd),
                "change_24h": str(change_24h_percent),
                "change_7d": str(change_7d_percent),
            },
            priority="normal",
        )
        return count > 0


def check_price_alerts_for_user(
    user_id: str,
    alerts: List[Dict[str, Any]],
    current_prices: Dict[str, float],
) -> int:
    """
    بررسی هشدارهای قیمتی یک کاربر و ارسال نوتیفیکیشن.
    
    Args:
        user_id: شناسه کاربر
        alerts: لیست هشدارها [{symbol, target_price, alert_type, ...}]
        current_prices: قیمت‌های فعلی {symbol: price}
        
    Returns:
        تعداد هشدارهای فعال شده
    """
    triggered = 0
    for alert in alerts:
        symbol = alert.get("symbol", "").upper()
        target = float(alert.get("target_price", 0))
        alert_type = alert.get("alert_type", "above")
        
        current = current_prices.get(symbol)
        if current is None:
            continue
        
        if alert_type == "above" and current >= target:
            PriceAlertNotifier.notify_price_alert(
                user_id, symbol, current, target, "above"
            )
            triggered += 1
        elif alert_type == "below" and current <= target:
            PriceAlertNotifier.notify_price_alert(
                user_id, symbol, current, target, "below"
            )
            triggered += 1
    
    return triggered


def calculate_portfolio_summary(user_id: str) -> Optional[Dict[str, Any]]:
    """
    محاسبه خلاصه پورتفوی برای یک کاربر از دیتابیس.
    
    Returns:
        دیکشنری包含 total_balance_usd, change_24h_percent, change_7d_percent
        یا None اگر کاربر دارایی ندارد
    """
    if not _lazy_init():
        return None
    
    try:
        session = _db_session()
        try:
            wallet_ids = [
                w.WalletID for w in session.query(_Wallets_model)
                .filter(_Wallets_model.UserID == user_id)
                .all()
            ]
            if not wallet_ids:
                return None
            
            # Get holdings
            holdings = session.query(_UserHolding_model).filter(
                _UserHolding_model.WalletID.in_(wallet_ids)
            ).all()
            
            if not holdings:
                return None
            
            total_usd = 0.0
            top_holding_symbol = None
            top_holding_value = 0.0
            
            for h in holdings:
                try:
                    value = float(h.Balance) if h.Balance else 0
                    total_usd += value
                    
                    # Track top holding (we use TokenSymbol as identifier)
                    symbol = h.TokenSymbol or "Unknown"
                    if value > top_holding_value:
                        top_holding_value = value
                        top_holding_symbol = symbol
                except (ValueError, TypeError):
                    continue
            
            if total_usd == 0:
                return None
            
            return {
                "total_balance_usd": total_usd,
                "top_holding": top_holding_symbol,
            }
        finally:
            session.close()
    except Exception as e:
        logger.error(f"calculate_portfolio_summary error: {e}")
        return None
