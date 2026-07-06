"""
Priority 4 — Network & Blockchain Status Notifications
=========================================================
نوتیفیکیشن‌های شبکه و بلاکچین:
- کارمزد بالای شبکه (High Gas Fees)
- آپدیت‌ها و فورک‌های شبکه (Network Upgrades/Forks)
- وضعیت شبکه (Network Status)
"""

from typing import Optional, Dict, Any
from utils.logging_config import get_logger
from .base import send_push_to_user, send_push_to_all_users

logger = get_logger(__file__)


class NetworkNotifier:
    """مدیریت نوتیفیکیشن‌های شبکه و بلاکچین."""

    # Thresholds for gas fee alerts (in Gwei for EVM chains)
    GAS_THRESHOLDS: Dict[str, Dict[str, float]] = {
        "ethereum": {"high": 100, "very_high": 200},
        "bsc": {"high": 10, "very_high": 20},
        "polygon": {"high": 200, "very_high": 500},
        "arbitrum": {"high": 1.0, "very_high": 2.0},
        "optimism": {"high": 0.1, "very_high": 0.5},
    }

    @staticmethod
    def notify_high_gas(
        user_id: str,
        blockchain: str,
        gas_price_gwei: float,
        level: str = "high",  # high, very_high
    ) -> bool:
        """
        ارسال نوتیفیکیشن هنگام افزایش کارمزد شبکه.
        
        Args:
            user_id: شناسه کاربر
            blockchain: نام بلاکچین (مثلاً ethereum)
            gas_price_gwei: قیمت گاز فعلی به Gwei
            level: سطح هشدار (high, very_high)
            
        Returns:
            bool: موفقیت
        """
        icon = "🔥" if level == "very_high" else "⚠️"
        level_label = "Very High" if level == "very_high" else "High"
        
        title = f"{icon} {blockchain.title()} Gas: {level_label}"
        body = f"Gas fee is {gas_price_gwei:.1f} Gwei. Consider waiting for lower fees."

        count = send_push_to_user(
            user_id=user_id,
            title=title,
            body=body,
            data={
                "type": "gas_alert",
                "blockchain": blockchain,
                "gas_price_gwei": str(gas_price_gwei),
                "level": level,
            },
            priority="normal",
        )
        return count > 0

    @staticmethod
    def notify_network_status(
        user_id: Optional[str],
        blockchain: str,
        status: str,  # maintenance, outage, degraded, restored
        message: str,
    ) -> int:
        """
        اطلاع‌رسانی درباره وضعیت شبکه.
        
        Args:
            user_id: شناسه کاربر (None برای broadcast به همه)
            blockchain: نام بلاکچین
            status: وضعیت
            message: توضیحات
            
        Returns:
            تعداد دستگاه‌های notified
        """
        icons = {
            "maintenance": "🔧",
            "outage": "🚨",
            "degraded": "⚠️",
            "restored": "✅",
        }
        icon = icons.get(status, "ℹ️")
        
        status_labels = {
            "maintenance": "Under Maintenance",
            "outage": "Network Outage",
            "degraded": "Performance Degraded",
            "restored": "Service Restored",
        }
        label = status_labels.get(status, status.title())
        
        title = f"{icon} {blockchain.title()} — {label}"
        body = message

        data = {
            "type": "network_status",
            "blockchain": blockchain,
            "status": status,
            "message": message,
        }

        if user_id:
            count = send_push_to_user(user_id, title, body, data, priority="high")
        else:
            count = send_push_to_all_users(title, body, data, priority="high")
        
        logger.info(f"Network: {blockchain} {status} notified to {count} devices")
        return count

    @staticmethod
    def notify_network_upgrade(
        blockchain: str,
        upgrade_name: str,
        description: str,
        estimated_time: Optional[str] = None,
    ) -> int:
        """
        اطلاع‌رسانی درباره آپگرید یا هاردفورک شبکه.
        
        Args:
            blockchain: نام بلاکچین
            upgrade_name: نام آپگرید (مثلاً Dencun, Shanghai)
            description: توضیحات
            estimated_time: زمان تخمینی
            
        Returns:
            تعداد دستگاه‌های notified
        """
        title = f"🔄 {blockchain.title()} Upgrade: {upgrade_name}"
        
        body_parts = [description]
        if estimated_time:
            body_parts.append(f"Estimated: {estimated_time}")
        body = " · ".join(body_parts)

        count = send_push_to_all_users(
            title=title,
            body=body,
            data={
                "type": "network_upgrade",
                "blockchain": blockchain,
                "upgrade_name": upgrade_name,
                "estimated_time": estimated_time or "",
            },
            priority="normal",
        )
        return count
