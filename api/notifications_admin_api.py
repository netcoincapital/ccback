"""
Admin Notification API
======================
API endpoints for:
- Security events (Priority 2)
- Price alerts (Priority 3) — supports both custom price & percentage-based alerts
- Broadcast / Engagement (Priority 5)

Database: dedicated `price_alerts` table (ORM: database.price_alert.PriceAlert)
Backward compatible with old `settings`-based storage.

Price Alert Types:
  Custom (قیمت دقیق):
    - alert_type: "above" | "below"
    - target_price: قیمت هدف (عدد)

  Quick / Percentage (درصدی):
    - alert_type: "percent_up" | "percent_down"
    - target_percent: درصد تغییر (مثلاً 10 یعنی 10%)
    - reference_price: قیمت لحظه ایجاد (خودکار ثبت می‌شود)
"""

import json
import time
import threading
from typing import Dict, List, Optional, Tuple, Any

from flask import Blueprint, request, jsonify
from utils.logging_config import get_logger
from utils.error_handlers import handle_api_errors
from sqlalchemy import text as sa_text

logger = get_logger(__file__)
notifications_admin_bp = Blueprint('notifications_admin', __name__)

_db_session_factory = None
_lock = threading.Lock()
_table_initialized = False


def _ensure_table():
    """Lazy table initialization — runs exactly once per process."""
    global _table_initialized
    if _table_initialized:
        return
    with _lock:
        if _table_initialized:
            return
        _init_price_alerts_table()
        _table_initialized = True

# ============================================================
# درون‌حافظه کش برای Price Alerts (TTL = 30 ثانیه)
# ============================================================
_cache: Dict[str, Tuple[float, Any]] = {}
_CACHE_TTL = 30  # seconds


def _cache_get(key: str) -> Optional[Any]:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, value = entry
    if time.monotonic() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    return value


def _cache_set(key: str, value: Any):
    _cache[key] = (time.monotonic(), value)


def _cache_invalidate(pattern: str = "price_alerts:"):
    to_delete = [k for k in _cache if k.startswith(pattern)]
    for k in to_delete:
        _cache.pop(k, None)


def _get_session():
    global _db_session_factory
    if _db_session_factory is None:
        from database import SessionLocal
        _db_session_factory = SessionLocal
    return _db_session_factory()


def _init_price_alerts_table():
    """Create price_alerts table via raw SQL (belt-and-suspenders with ORM create_all)."""
    try:
        session = _get_session()
        try:
            session.execute(sa_text("""
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    symbol VARCHAR(10) NOT NULL,
                    alert_type VARCHAR(20) NOT NULL,
                    target_price DECIMAL(20, 8) NULL,
                    target_percent DECIMAL(10, 2) NULL,
                    reference_price DECIMAL(20, 8) NULL,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_price_alerts_user (user_id),
                    INDEX idx_price_alerts_symbol (symbol),
                    INDEX idx_price_alerts_active (is_active)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            session.commit()
            logger.info("price_alerts table ensured at module init")
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error creating price_alerts table: {e}")


# Note: Table creation is lazy — _init_price_alerts_table() runs on first API call.
# This avoids import-time deadlocks with the Gunicorn worker pool.


def _fetch_current_price(symbol: str) -> Optional[float]:
    """
    دریافت قیمت لحظه‌ای یک سمبل از V2 price cache (RAM, TTL ~2 دقیقه).
    """
    try:
        from services.cache_proxy.price_cache import get_price_cache
        pc = get_price_cache()
        all_prices = pc.get_all_prices()
        entry = all_prices.get(symbol.upper())
        if entry and entry.get("price") is not None:
            return float(entry["price"])
    except Exception as e:
        logger.debug(f"Could not fetch current price for {symbol}: {e}")

    # Fallback: از دیتابیس
    try:
        session = _get_session()
        try:
            # New schema
            row = session.execute(sa_text("""
                SELECT cp.price FROM current_prices cp
                INNER JOIN symbols s ON s.id = cp.symbol_id
                WHERE s.symbol = :sym
                LIMIT 1
            """), {"sym": symbol.upper()}).first()
            if row:
                return float(row[0])
            # Old schema
            row = session.execute(sa_text("""
                SELECT p.price FROM prices p
                INNER JOIN currencies c ON p.crypto_id = c.CurrencyID
                WHERE c.Symbol = :sym AND p.currency = 'USD' AND p.is_historical = 0
                ORDER BY p.last_updated DESC LIMIT 1
            """), {"sym": symbol.upper()}).first()
            if row:
                return float(row[0])
        finally:
            session.close()
    except Exception as e:
        logger.debug(f"DB price fallback failed for {symbol}: {e}")

    return None


# ============================================================
# Security Notifications (Priority 2)
# ============================================================

@notifications_admin_bp.route('/notifications/security/login', methods=['POST'])
@handle_api_errors
def notify_security_login():
    """Notify user of login from new device."""
    data = request.get_json() or {}
    user_id = data.get('UserID')
    if not user_id:
        return jsonify({"success": False, "message": "UserID is required"}), 400

    from services.notifications.security import SecurityNotifier
    result = SecurityNotifier.notify_new_login(
        user_id=user_id,
        device_name=data.get('DeviceName', 'Unknown Device'),
        device_type=data.get('DeviceType', 'unknown'),
        ip_address=data.get('IPAddress', ''),
        location=data.get('Location'),
    )

    return jsonify({
        "success": result,
        "message": "Security notification sent" if result else "No devices to notify",
    })


@notifications_admin_bp.route('/notifications/security/change', methods=['POST'])
@handle_api_errors
def notify_security_change():
    data = request.get_json() or {}
    user_id = data.get('UserID')
    change_type = data.get('ChangeType')

    if not user_id:
        return jsonify({"success": False, "message": "UserID is required"}), 400
    if not change_type:
        return jsonify({"success": False, "message": "ChangeType is required"}), 400

    valid_types = ['password_changed', 'pin_changed', '2fa_enabled', '2fa_disabled']
    if change_type not in valid_types:
        return jsonify({"success": False, "message": f"Invalid ChangeType. Valid: {valid_types}"}), 400

    from services.notifications.security import SecurityNotifier
    result = SecurityNotifier.notify_security_change(
        user_id=user_id,
        change_type=change_type,
        device_name=data.get('DeviceName'),
    )

    return jsonify({
        "success": result,
        "message": "Security notification sent" if result else "No devices to notify",
    })


@notifications_admin_bp.route('/notifications/security/suspicious', methods=['POST'])
@handle_api_errors
def notify_security_suspicious():
    data = request.get_json() or {}
    user_id = data.get('UserID')
    if not user_id:
        return jsonify({"success": False, "message": "UserID is required"}), 400

    from services.notifications.security import SecurityNotifier
    result = SecurityNotifier.notify_suspicious_activity(
        user_id=user_id,
        activity_type=data.get('ActivityType', 'unknown'),
        description=data.get('Description', 'Suspicious activity detected'),
        severity=data.get('Severity', 'warning'),
    )

    return jsonify({
        "success": result,
        "message": "Security notification sent" if result else "No devices to notify",
    })


# ============================================================
# Price Alert Subscriptions (Priority 3) — NEW: dual-type
# ============================================================

VALID_ALERT_TYPES = frozenset({"above", "below", "percent_up", "percent_down"})


@notifications_admin_bp.route('/notifications/price-alert', methods=['POST'])
@handle_api_errors
def create_price_alert():
    """
    Create a new price alert.

    Non-custodial (recommended):
        { "DeviceID": "UUID-v4", "Symbol":"BTC", "AlertType":"above", "TargetPrice": 50000 }

    Backward compatible:
        { "UserID": "...", "Symbol":"BTC", "AlertType":"above", "TargetPrice": 50000 }
    """
    _ensure_table()
    data = request.get_json() or {}

    # Phase 1: رفع شناسه — اول DeviceID (جدید)، بعد UserID (قدیمی)
    device_id = data.get('DeviceID')
    user_id = data.get('UserID')
    identifier = device_id or user_id
    is_anonymous = bool(device_id)  # True = حالت non-custodial

    symbol = data.get('Symbol', '').upper().strip()
    alert_type = data.get('AlertType', '').lower().strip()

    if not identifier or not symbol:
        return jsonify({
            "success": False,
            "message": "DeviceID (یا UserID) و Symbol الزامی هستند"
        }), 400
    if alert_type not in VALID_ALERT_TYPES:
        return jsonify({
            "success": False,
            "message": f"AlertType must be one of: {', '.join(sorted(VALID_ALERT_TYPES))}"
        }), 400

    from database.price_alert import PriceAlert
    session = _get_session()
    try:
        if alert_type in ("above", "below"):
            # ─── Custom price alert ───
            target_price = data.get('TargetPrice')
            if target_price is None:
                return jsonify({"success": False, "message": "TargetPrice is required for above/below alerts"}), 400
            try:
                target_price = float(target_price)
            except (ValueError, TypeError):
                return jsonify({"success": False, "message": "Invalid TargetPrice"}), 400
            if target_price <= 0:
                return jsonify({"success": False, "message": "TargetPrice must be positive"}), 400

            alert = PriceAlert(
                user_id=identifier,
                symbol=symbol,
                alert_type=alert_type,
                target_price=target_price,
                is_active=True,
            )
            session.add(alert)
            session.commit()
            logger.info(
                f"Price alert created: {symbol} {alert_type} ${target_price:,.2f} "
                f"for {'anonymous' if is_anonymous else 'user'} {identifier[:12]}..."
            )
            return jsonify({
                "success": True,
                "alert": alert.to_dict(),
                "message": f"Price alert set: {symbol} {alert_type} ${target_price:,.2f}",
            }), 201

        else:
            # ─── Quick percentage alert ───
            target_percent = data.get('TargetPercent')
            if target_percent is None:
                return jsonify({"success": False, "message": "TargetPercent is required for percent_up/percent_down alerts"}), 400
            try:
                target_percent = float(target_percent)
            except (ValueError, TypeError):
                return jsonify({"success": False, "message": "Invalid TargetPercent"}), 400
            if target_percent <= 0:
                return jsonify({"success": False, "message": "TargetPercent must be positive"}), 400
            if target_percent > 1000:
                return jsonify({"success": False, "message": "TargetPercent cannot exceed 1000%"}), 400

            # Capture current price as reference
            reference_price = _fetch_current_price(symbol)
            if reference_price is None:
                return jsonify({
                    "success": False,
                    "message": f"Could not fetch current price for {symbol}. Try again later."
                }), 503

            alert = PriceAlert(
                user_id=identifier,
                symbol=symbol,
                alert_type=alert_type,
                target_percent=target_percent,
                reference_price=reference_price,
                is_active=True,
            )
            session.add(alert)
            session.commit()

            direction = "📈" if alert_type == "percent_up" else "📉"
            logger.info(
                f"Quick alert created: {symbol} {direction} {target_percent}% "
                f"(ref: ${reference_price:,.2f}) for {'anonymous' if is_anonymous else 'user'} {identifier[:12]}..."
            )
            return jsonify({
                "success": True,
                "alert": alert.to_dict(),
                "message": (
                    f"Alert set: {symbol} {direction} {target_percent}% "
                    f"(current: ${reference_price:,.2f})"
                ),
            }), 201

    except Exception as e:
        session.rollback()
        logger.error(f"Error creating price alert: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        session.close()


@notifications_admin_bp.route('/notifications/price-alerts/<user_id>', methods=['GET'])
@handle_api_errors
def get_price_alerts(user_id):
    _ensure_table()
    """
    Get all active price alerts for a user.

    Returns alerts from BOTH sources:
      1. New price_alerts table (primary)
      2. Legacy settings table (backward compatible)

    Uses in-memory cache (TTL=30s).
    """
    cache_key = f"price_alerts:{user_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return jsonify({"success": True, "alerts": cached, "cached": True})

    from database.price_alert import PriceAlert
    session = _get_session()
    try:
        alerts = []

        # 1. New table
        try:
            rows = (
                session.query(PriceAlert)
                .filter(PriceAlert.user_id == user_id, PriceAlert.is_active == True)
                .order_by(PriceAlert.created_at.desc())
                .all()
            )
            for r in rows:
                alerts.append(r.to_dict())
        except Exception as e:
            logger.debug(f"New table query failed: {e}")

        # 2. Legacy settings table (for backward compatibility during migration)
        try:
            legacy = session.execute(sa_text("""
                SELECT setting_key, setting_value FROM settings
                WHERE setting_key LIKE :pattern
            """), {"pattern": f"price_alert:{user_id}:%"})
            for row in legacy:
                parts = row.setting_key.split(":")
                if len(parts) >= 4:
                    alerts.append({
                        "id": None,
                        "symbol": parts[2],
                        "alert_type": parts[3],
                        "target_price": float(row.setting_value) if row.setting_value else 0,
                        "is_active": True,
                        "note": "Legacy (settings table)",
                    })
        except Exception:
            pass  # settings table may not exist

        # Remove duplicates (new table takes priority)
        seen = set()
        unique_alerts = []
        for a in alerts:
            dedup_key = (a["symbol"], a["alert_type"], a.get("target_price"))
            if dedup_key not in seen:
                seen.add(dedup_key)
                unique_alerts.append(a)

        _cache_set(cache_key, unique_alerts)
        return jsonify({"success": True, "alerts": unique_alerts})

    except Exception as e:
        logger.error(f"Error getting price alerts: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        session.close()


@notifications_admin_bp.route('/notifications/price-alert', methods=['DELETE'])
@handle_api_errors
def delete_price_alert():
    _ensure_table()
    """
    Delete a price alert.

    Non-custodial:
        { "DeviceID": "UUID-v4", "AlertID": 1 }
        { "DeviceID": "UUID-v4", "Symbol": "BTC", "AlertType": "above" }

    Backward compatible:
        { "UserID": "...", "AlertID": 1 }
        { "UserID": "...", "Symbol": "BTC", "AlertType": "above" }
    """
    data = request.get_json() or {}
    device_id = data.get('DeviceID')
    user_id = data.get('UserID')
    identifier = device_id or user_id
    if not identifier:
        return jsonify({"success": False, "message": "DeviceID (یا UserID) الزامی است"}), 400

    from database.price_alert import PriceAlert
    session = _get_session()
    try:
        alert_id = data.get('AlertID')

        if alert_id is not None:
            # ─── Delete by ID (preferred) ───
            try:
                alert_id = int(alert_id)
            except (ValueError, TypeError):
                return jsonify({"success": False, "message": "Invalid AlertID"}), 400

            alert = (
                session.query(PriceAlert)
                .filter(PriceAlert.id == alert_id, PriceAlert.user_id == identifier)
                .first()
            )
            if not alert:
                return jsonify({"success": False, "message": "Alert not found"}), 404

            session.delete(alert)
            session.commit()
            _cache_invalidate(f"price_alerts:{identifier}")
            return jsonify({"success": True, "message": f"Alert #{alert_id} deleted"})

        else:
            # ─── Delete by Symbol + AlertType (backward compatible) ───
            symbol = data.get('Symbol', '').upper().strip()
            alert_type = data.get('AlertType', '').lower().strip()

            if not symbol:
                return jsonify({"success": False, "message": "AlertID or Symbol required"}), 400

            # Delete from new table
            deleted_new = (
                session.query(PriceAlert)
                .filter(
                    PriceAlert.user_id == identifier,
                    PriceAlert.symbol == symbol,
                    PriceAlert.alert_type == alert_type,
                )
                .delete()
            )

            # Delete from legacy settings table
            deleted_legacy = 0
            try:
                key = f"price_alert:{identifier}:{symbol}:{alert_type}"
                result = session.execute(
                    sa_text("DELETE FROM settings WHERE setting_key = :key"),
                    {"key": key}
                )
                deleted_legacy = result.rowcount
            except Exception:
                pass

            session.commit()
            _cache_invalidate(f"price_alerts:{identifier}")

            total = deleted_new + deleted_legacy
            if total == 0:
                return jsonify({"success": False, "message": f"No alert found for {symbol}"}), 404

            return jsonify({"success": True, "message": f"Alert for {symbol} removed ({total} deleted)"})

    except Exception as e:
        session.rollback()
        logger.error(f"Error deleting price alert: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        session.close()


@notifications_admin_bp.route('/notifications/price-alerts/prices', methods=['GET'])
@handle_api_errors
def get_price_alert_prices():
    _ensure_table()
    """
    Bulk price endpoint — دریافت قیمت‌های لحظه‌ای برای یک یا چند سمبل.

    Query Parameters:
        symbols (str): سمبل‌های مورد نظر با کاما (مثلاً BTC,ETH,SOL)

    Returns:
        200: {"success": true, "prices": {"BTC": 50000.0, "ETH": 3000.0}}
    """
    symbols_str = request.args.get("symbols", "").strip()
    if not symbols_str:
        return jsonify({"success": False, "message": "symbols query parameter is required"}), 400

    symbols = [s.upper().strip() for s in symbols_str.split(",") if s.strip()]
    if not symbols:
        return jsonify({"success": False, "message": "No valid symbols provided"}), 400

    try:
        from services.cache_proxy.price_cache import get_price_cache
        pc = get_price_cache()
        all_prices = pc.get_all_prices()

        result = {}
        for sym in symbols:
            entry = all_prices.get(sym)
            if entry and entry.get("price") is not None:
                result[sym] = float(entry["price"])
            else:
                result[sym] = None

        return jsonify({"success": True, "prices": result, "count": len(result)})
    except Exception as e:
        logger.error(f"Error fetching bulk prices: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ============================================================
# Broadcast / Engagement (Priority 5) — unchanged
# ============================================================

@notifications_admin_bp.route('/admin/notifications/broadcast', methods=['POST'])
@handle_api_errors
def admin_broadcast():
    data = request.get_json() or {}
    title = data.get('Title')
    body = data.get('Body')
    if not title or not body:
        return jsonify({"success": False, "message": "Title and Body are required"}), 400

    broadcast_type = data.get('Type', 'general')
    extra_data = data.get('Data', {})

    from services.notifications.base import send_push_to_all_users
    push_data = {"type": broadcast_type, "admin_broadcast": "true", **extra_data}
    count = send_push_to_all_users(
        title=title, body=body, data=push_data,
        priority=data.get('Priority', 'high'),
    )
    return jsonify({"success": True, "message": f"Broadcast sent to {count} devices", "devices_notified": count})


@notifications_admin_bp.route('/admin/notifications/new-listing', methods=['POST'])
@handle_api_errors
def admin_new_listing():
    data = request.get_json() or {}
    symbol = data.get('Symbol')
    name = data.get('Name')
    if not symbol or not name:
        return jsonify({"success": False, "message": "Symbol and Name are required"}), 400
    from services.notifications.engagement import EngagementNotifier
    count = EngagementNotifier.notify_new_listing(
        symbol=symbol, name=name,
        blockchain=data.get('Blockchain', ''),
        description=data.get('Description'),
    )
    return jsonify({"success": True, "message": f"New listing notification sent to {count} devices"})


@notifications_admin_bp.route('/admin/notifications/breaking-news', methods=['POST'])
@handle_api_errors
def admin_breaking_news():
    data = request.get_json() or {}
    title = data.get('Title')
    body = data.get('Body')
    if not title or not body:
        return jsonify({"success": False, "message": "Title and Body are required"}), 400
    from services.notifications.engagement import EngagementNotifier
    count = EngagementNotifier.notify_breaking_news(
        title_news=title, body_news=body, url=data.get('URL'),
    )
    return jsonify({"success": True, "message": f"Breaking news sent to {count} devices"})


@notifications_admin_bp.route('/admin/notifications/app-update', methods=['POST'])
@handle_api_errors
def admin_app_update():
    data = request.get_json() or {}
    version = data.get('Version')
    changes = data.get('Changes', [])
    if not version:
        return jsonify({"success": False, "message": "Version is required"}), 400
    from services.notifications.engagement import EngagementNotifier
    count = EngagementNotifier.notify_app_update(
        version=version,
        changes=changes if isinstance(changes, list) else [str(changes)],
        force_update=data.get('ForceUpdate', False),
    )
    return jsonify({"success": True, "message": f"App update notification sent to {count} devices"})


@notifications_admin_bp.route('/admin/notifications/portfolio-summary/<user_id>', methods=['POST'])
@handle_api_errors
def trigger_portfolio_summary(user_id):
    from services.notifications.price_alerts import calculate_portfolio_summary, PriceAlertNotifier
    summary = calculate_portfolio_summary(user_id)
    if not summary:
        return jsonify({"success": False, "message": "No portfolio data found for this user"}), 404
    result = PriceAlertNotifier.notify_portfolio_summary(
        user_id=user_id,
        total_balance_usd=summary["total_balance_usd"],
        change_24h_percent=0, change_7d_percent=0,
        top_holding=summary.get("top_holding"),
    )
    return jsonify({
        "success": result,
        "message": "Portfolio summary sent" if result else "No devices to notify",
        "summary": summary,
    })


@notifications_admin_bp.route('/admin/notifications/reward', methods=['POST'])
@handle_api_errors
def send_reward_notification():
    data = request.get_json() or {}
    user_id = data.get('UserID')
    reward_type = data.get('RewardType', 'airdrop')
    amount = data.get('Amount', '0')
    symbol = data.get('Symbol', '')
    if not user_id or not symbol:
        return jsonify({"success": False, "message": "UserID and Symbol are required"}), 400
    from services.notifications.engagement import EngagementNotifier
    result = EngagementNotifier.notify_reward(
        user_id=user_id, reward_type=reward_type,
        amount=str(amount), symbol=symbol,
        description=data.get('Description'),
    )
    return jsonify({
        "success": result,
        "message": "Reward notification sent" if result else "No devices to notify",
    })


# ============================================================
# Network Status (Priority 4)
# ============================================================

@notifications_admin_bp.route('/admin/notifications/network-status', methods=['POST'])
@handle_api_errors
def admin_network_status():
    data = request.get_json() or {}
    blockchain = data.get('Blockchain')
    status = data.get('Status')
    message = data.get('Message')
    if not blockchain or not status or not message:
        return jsonify({"success": False, "message": "Blockchain, Status, and Message are required"}), 400
    user_id = data.get('UserID')
    from services.notifications.network import NetworkNotifier
    count = NetworkNotifier.notify_network_status(
        user_id=user_id, blockchain=blockchain,
        status=status, message=message,
    )
    return jsonify({"success": True, "message": f"Network status sent to {count} devices"})


@notifications_admin_bp.route('/admin/notifications/network-upgrade', methods=['POST'])
@handle_api_errors
def admin_network_upgrade():
    data = request.get_json() or {}
    blockchain = data.get('Blockchain')
    upgrade_name = data.get('UpgradeName')
    description = data.get('Description')
    if not blockchain or not upgrade_name:
        return jsonify({"success": False, "message": "Blockchain and UpgradeName are required"}), 400
    from services.notifications.network import NetworkNotifier
    count = NetworkNotifier.notify_network_upgrade(
        blockchain=blockchain, upgrade_name=upgrade_name,
        description=description or f"{upgrade_name} upgrade on {blockchain}",
        estimated_time=data.get('EstimatedTime'),
    )
    return jsonify({"success": True, "message": f"Network upgrade notification sent to {count} devices"})
