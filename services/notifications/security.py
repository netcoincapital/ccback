"""
Priority 2 — Security Notifications
=====================================
نوتیفیکیشن‌های امنیتی:
- ورود از دستگاه یا مکان جدید (New Login)
- تغییرات امنیتی (Security Changes)
- فعالیت مشکوک (Suspicious Activity)

این ماژول API endpoints دارد که فرانت‌اند باید در مواقع مناسب صدا بزند.
"""

from typing import Optional, Dict, Any
from utils.logging_config import get_logger
from .base import send_push_to_user

logger = get_logger(__file__)


class SecurityNotifier:
    """
    مدیریت نوتیفیکیشن‌های امنیتی.
    هر متد مربوط به یک نوع رویداد امنیتی است.
    """

    @staticmethod
    def notify_new_login(
        user_id: str,
        device_name: str,
        device_type: str,
        ip_address: str,
        location: Optional[str] = None,
    ) -> bool:
        """
        ارسال نوتیفیکیشن هنگام ورود از دستگاه یا موقعیت جدید.
        
        Args:
            user_id: شناسه کاربر
            device_name: نام دستگاه (مثلاً "Samsung Galaxy S24")
            device_type: نوع دستگاه (android/ios/web)
            ip_address: آدرس IP
            location: موقعیت جغرافیایی (اختیاری)
            
        Returns:
            bool: موفقیت
        """
        title = "🔐 New Login Detected"
        
        if location:
            body = f"New login from {device_name} · {location}"
        else:
            body = f"New login from {device_name} ({ip_address})"
        
        if device_type == "web":
            body = f"New web login · {device_name} ({ip_address})"

        count = send_push_to_user(
            user_id=user_id,
            title=title,
            body=body,
            data={
                "type": "security_login",
                "device_name": device_name,
                "device_type": device_type,
                "ip_address": ip_address,
                "location": location or "",
            },
            priority="high",
        )
        
        if count > 0:
            logger.info(f"Security: new login notification sent to user {user_id[:8]}...")
        else:
            logger.warning(f"Security: no devices to notify for new login (user {user_id[:8]}...)")
        
        return count > 0

    @staticmethod
    def notify_security_change(
        user_id: str,
        change_type: str,  # password_changed, pin_changed, 2fa_enabled, 2fa_disabled
        device_name: Optional[str] = None,
    ) -> bool:
        """
        ارسال نوتیفیکیشن هنگام تغییر تنظیمات امنیتی.
        
        Args:
            user_id: شناسه کاربر
            change_type: نوع تغییر (password_changed, pin_changed, 2fa_enabled, 2fa_disabled)
            device_name: نام دستگاه (اختیاری)
            
        Returns:
            bool: موفقیت
        """
        titles = {
            "password_changed": "🔑 Password Changed",
            "pin_changed": "🔑 PIN Changed",
            "2fa_enabled": "✅ Two-Factor Auth Enabled",
            "2fa_disabled": "⚠️ Two-Factor Auth Disabled",
        }
        
        messages = {
            "password_changed": "Your wallet password has been changed successfully.",
            "pin_changed": "Your wallet PIN has been changed successfully.",
            "2fa_enabled": "Two-factor authentication is now active on your account.",
            "2fa_disabled": "Two-factor authentication has been disabled on your account.",
        }
        
        title = titles.get(change_type, "🔐 Security Setting Changed")
        body = messages.get(change_type, f"Security setting changed: {change_type}")
        
        if device_name:
            body += f" from {device_name}"

        count = send_push_to_user(
            user_id=user_id,
            title=title,
            body=body,
            data={
                "type": "security_change",
                "change_type": change_type,
            },
            priority="high",
        )
        
        if count > 0:
            logger.info(f"Security: {change_type} notification sent to user {user_id[:8]}...")
        
        return count > 0

    @staticmethod
    def notify_suspicious_activity(
        user_id: str,
        activity_type: str,  # failed_login, unusual_transaction, etc.
        description: str,
        severity: str = "warning",  # info, warning, critical
    ) -> bool:
        """
        ارسال نوتیفیکیشن هنگام فعالیت مشکوک.
        
        Args:
            user_id: شناسه کاربر
            activity_type: نوع فعالیت مشکوک
            description: توضیحات
            severity: شدت (info, warning, critical)
            
        Returns:
            bool: موفقیت
        """
        icon = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🚨",
        }.get(severity, "⚠️")
        
        title = f"{icon} Suspicious Activity"
        body = description

        count = send_push_to_user(
            user_id=user_id,
            title=title,
            body=body,
            data={
                "type": "security_suspicious",
                "activity_type": activity_type,
                "severity": severity,
                "description": description,
            },
            priority="high",
        )
        
        logger.info(
            f"Security: suspicious activity ({severity}/{activity_type}) "
            f"notified for user {user_id[:8]}...: {count} devices"
        )
        return count > 0
