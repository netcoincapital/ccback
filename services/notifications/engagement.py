"""
Priority 5 — Engagement & Features Notifications
===================================================
نوتیفیکیشن‌های تعاملی:
- لیست شدن ارز جدید (New Listings)
- پاداش و ایردراپ (Rewards & Airdrops)
- اخبار فوری (Breaking News)
- به‌روزرسانی اپ (App Updates)

همه این نوتیفیکیشن‌ها از طریق Admin API ارسال می‌شوند.
"""

from typing import Optional, Dict, Any, List
from utils.logging_config import get_logger
from .base import send_push_to_user, send_push_to_all_users

logger = get_logger(__file__)


class EngagementNotifier:
    """مدیریت نوتیفیکیشن‌های تعاملی."""

    @staticmethod
    def notify_new_listing(
        symbol: str,
        name: str,
        blockchain: str,
        description: Optional[str] = None,
    ) -> int:
        """
        اطلاع‌رسانی اضافه شدن ارز جدید به همه کاربران.
        
        Args:
            symbol: نماد ارز (مثلاً PEPE)
            name: نام کامل (مثلاً Pepe Coin)
            blockchain: بلاکچین
            description: توضیحات اضافی
            
        Returns:
            تعداد دستگاه‌های notified
        """
        title = f"🪙 New Listing: {symbol}"
        body = f"{name} is now available on {blockchain.title()}"
        if description:
            body += f" · {description}"

        count = send_push_to_all_users(
            title=title,
            body=body,
            data={
                "type": "new_listing",
                "symbol": symbol,
                "name": name,
                "blockchain": blockchain,
            },
            priority="normal",
        )
        return count

    @staticmethod
    def notify_reward(
        user_id: str,
        reward_type: str,  # staking, airdrop, cashback, referral
        amount: str,
        symbol: str,
        description: Optional[str] = None,
    ) -> bool:
        """
        ارسال نوتیفیکیشن پاداش به یک کاربر خاص.
        
        Args:
            user_id: شناسه کاربر
            reward_type: نوع پاداش
            amount: مقدار
            symbol: نماد ارز
            description: توضیحات
            
        Returns:
            bool: موفقیت
        """
        icons = {
            "staking": "💰",
            "airdrop": "🎁",
            "cashback": "💵",
            "referral": "🤝",
        }
        icon = icons.get(reward_type, "🎉")
        
        titles = {
            "staking": f"{icon} Staking Reward: {amount} {symbol}",
            "airdrop": f"{icon} Airdrop: {amount} {symbol}",
            "cashback": f"{icon} Cashback: {amount} {symbol}",
            "referral": f"{icon} Referral Bonus: {amount} {symbol}",
        }
        title = titles.get(reward_type, f"{icon} Reward: {amount} {symbol}")
        
        bodies = {
            "staking": f"Your staking rewards for {symbol} have been deposited!",
            "airdrop": f"You received {amount} {symbol} airdrop!",
            "cashback": f"Cashback of {amount} {symbol} has been credited.",
            "referral": f"You earned {amount} {symbol} from your referral!",
        }
        body = bodies.get(reward_type, description or f"You received {amount} {symbol}")

        count = send_push_to_user(
            user_id=user_id,
            title=title,
            body=body,
            data={
                "type": "reward",
                "reward_type": reward_type,
                "amount": amount,
                "symbol": symbol,
            },
            priority="high",
        )
        return count > 0

    @staticmethod
    def notify_breaking_news(
        title_news: str,
        body_news: str,
        url: Optional[str] = None,
    ) -> int:
        """
        انتشار اخبار فوری به همه کاربران.
        
        Args:
            title_news: عنوان خبر
            body_news: متن خبر
            url: لینک مطلب کامل (اختیاری)
            
        Returns:
            تعداد دستگاه‌های notified
        """
        title = f"📰 {title_news}"
        body = body_news

        data = {
            "type": "breaking_news",
            "title": title_news,
            "body": body_news,
        }
        if url:
            data["url"] = url

        count = send_push_to_all_users(
            title=title,
            body=body,
            data=data,
            priority="high",
        )
        return count

    @staticmethod
    def notify_app_update(
        version: str,
        changes: List[str],
        force_update: bool = False,
    ) -> int:
        """
        اطلاع‌رسانی نسخه جدید اپلیکیشن به همه کاربران.
        
        Args:
            version: شماره نسخه (مثلاً 2.4.0)
            changes: لیست تغییرات
            force_update: آیا آپدیت اجباری است
            
        Returns:
            تعداد دستگاه‌های notified
        """
        prefix = "🔴" if force_update else "🆕"
        title = f"{prefix} App Update v{version}"
        
        if force_update:
            title = f"🔴 Important: Update Required v{version}"
        
        body = " · ".join(changes[:3])  # حداکثر ۳ تغییر
        if len(changes) > 3:
            body += f" · +{len(changes) - 3} more"

        count = send_push_to_all_users(
            title=title,
            body=body,
            data={
                "type": "app_update",
                "version": version,
                "changes": json.dumps(changes),
                "force_update": str(force_update).lower(),
            },
            priority="high" if force_update else "normal",
        )
        return count


# HACK: need json import for the changes serialization
import json
