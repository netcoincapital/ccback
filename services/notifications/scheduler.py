"""
Background Scheduler for Periodic Notifications
================================================
این ماژول وظایف دوره‌ای زیر را اجرا می‌کند:

1. Gas Alert Scheduler: هر ۵ دقیقه کارمزد شبکه را بررسی می‌کند
   و اگر از حد مجاز بالاتر بود هشدار می‌دهد.

2. Price Alert Scheduler: هر ۱۰ دقیقه قیمت‌ها را بررسی می‌کند
   و هشدارهای قیمتی کاربران را فعال می‌کند.

3. Portfolio Summary Scheduler: هر ۲۴ ساعت یکبار گزارش پورتفوی
   می‌فرستد.
"""

import time
import threading
import json
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

from utils.logging_config import get_logger
from .base import get_all_user_ids
from .price_alerts import check_price_alerts_for_user, calculate_portfolio_summary, PriceAlertNotifier
from .network import NetworkNotifier

logger = get_logger(__file__)

# Settings table for persisting state
_db_session_factory = None


def _get_session():
    global _db_session_factory
    if _db_session_factory is None:
        from database import SessionLocal
        _db_session_factory = SessionLocal
    return _db_session_factory()


def _ensure_table():
    """Create settings table if it doesn't exist."""
    from sqlalchemy import text
    try:
        session = _get_session()
        try:
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    setting_key VARCHAR(100) NOT NULL UNIQUE,
                    setting_value TEXT,
                    description VARCHAR(255),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """))
            session.commit()
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Scheduler: error ensuring settings table: {e}")


def _get_setting(key: str, default: str = "") -> str:
    """خواندن یک تنظیم از جدول settings."""
    from sqlalchemy import text
    _ensure_table()
    try:
        session = _get_session()
        try:
            result = session.execute(
                text("SELECT setting_value FROM settings WHERE setting_key = :key"),
                {"key": key}
            ).first()
            return result.setting_value if result else default
        finally:
            session.close()
    except Exception as e:
        logger.debug(f"Scheduler: _get_setting error: {e}")
        return default


def _set_setting(key: str, value: str):
    """نوشتن یک تنظیم در جدول settings."""
    from sqlalchemy import text
    _ensure_table()
    try:
        session = _get_session()
        try:
            session.execute(text("""
                INSERT INTO settings (setting_key, setting_value)
                VALUES (:key, :value)
                ON DUPLICATE KEY UPDATE setting_value = :value2
            """), {"key": key, "value": value, "value2": value})
            session.commit()
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Scheduler: _set_setting error: {e}")


# ============================================================
# Gas Alert Checker (every 5 minutes)
# ============================================================

def _check_gas_prices():
    """بررسی کارمزد شبکه‌ها و ارسال هشدار اگر بالای threshold باشد."""
    try:
        # Create a local instance to get current gas data
        from services.cache_proxy.gas_cache import GasCache
        gas_checker = GasCache(ttl_seconds=0)  # Force refresh
        gas_data = gas_checker.get_all_gas()
        if not gas_data:
            return

        # Check EVM chains against thresholds
        for chain, thresholds in NetworkNotifier.GAS_THRESHOLDS.items():
            chain_gas = gas_data.get(chain) or gas_data.get(chain.capitalize())
            if not chain_gas:
                continue
            
            # Try to get gas price (handle different response formats)
            gas_gwei = None
            if isinstance(chain_gas, dict):
                gas_gwei = (
                    chain_gas.get("gas_price") or 
                    chain_gas.get("gasPrice") or 
                    chain_gas.get("fast") or
                    chain_gas.get("proposeGasPrice")
                )
            
            if gas_gwei is None:
                continue
            
            try:
                gas_gwei = float(gas_gwei)
            except (ValueError, TypeError):
                continue
            
            # Check if gas is above very_high threshold
            very_high = thresholds.get("very_high", float("inf"))
            high = thresholds.get("high", float("inf"))
            
            last_notified_key = f"gas_notified_{chain}"
            last_level = _get_setting(last_notified_key, "")
            
            if gas_gwei >= very_high and last_level != "very_high":
                _set_setting(last_notified_key, "very_high")
                logger.info(f"Gas: {chain} is very high ({gas_gwei} Gwei) - broadcasting alert")
                
                # Notify users who might transact
                _notify_gas_alert_to_active_users(chain, gas_gwei, "very_high")
                
            elif gas_gwei >= high and last_level != "high":
                _set_setting(last_notified_key, "high")
                logger.info(f"Gas: {chain} is high ({gas_gwei} Gwei) - broadcasting alert")
                _notify_gas_alert_to_active_users(chain, gas_gwei, "high")
                
            elif gas_gwei < high and last_level in ("high", "very_high"):
                _set_setting(last_notified_key, "normal")
                logger.info(f"Gas: {chain} returned to normal ({gas_gwei} Gwei)")
                
    except Exception as e:
        logger.debug(f"Gas checker error: {e}")


def _notify_gas_alert_to_active_users(blockchain: str, gas_gwei: float, level: str):
    """ارسال هشدار گاز به کاربرانی که در آن شبکه تراکنش داشته‌اند."""
    try:
        from database import SessionLocal, Transfers, Wallets
        from .base import get_device_tokens_for_wallets
        
        session = SessionLocal()
        try:
            # Find wallets that recently transacted on this chain
            from sqlalchemy import func
            from database.Blockchains import Blockchains
            
            recent_wallets = session.query(
                Wallets.WalletID
            ).join(
                Transfers, Transfers.WalletID == Wallets.WalletID
            ).join(
                Blockchains, Transfers.BlockchainID == Blockchains.BlockchainID
            ).filter(
                Blockchains.BlockchainName.ilike(f"%{blockchain}%"),
                Transfers.Timestamp >= datetime.utcnow() - timedelta(hours=24)
            ).distinct().all()
            
            wallet_ids = [w.WalletID for w in recent_wallets[:100]]  # limit
            if not wallet_ids:
                return
            
            tokens = get_device_tokens_for_wallets(wallet_ids)
            from config.firebase import send_notification
            
            icon = "🔥" if level == "very_high" else "⚠️"
            level_label = "Very High" if level == "very_high" else "High"
            
            for token in tokens:
                try:
                    send_notification(
                        token=token,
                        title=f"{icon} {blockchain.title()} Gas: {level_label}",
                        body=f"Gas fee is {gas_gwei:.1f} Gwei. Consider waiting.",
                        data={
                            "type": "gas_alert",
                            "blockchain": blockchain,
                            "gas_price_gwei": str(gas_gwei),
                            "level": level,
                        },
                        priority="normal",
                    )
                except Exception:
                    pass
                    
            logger.info(f"Gas: notified {len(tokens)} devices about {blockchain} ({level})")
        finally:
            session.close()
    except Exception as e:
        logger.debug(f"_notify_gas_alert_to_active_users: {e}")


# ============================================================
# Price Alert Checker (every 10 minutes)
# ============================================================

def _get_current_prices(session, symbols):
    """
    دریافت قیمت‌های فعلی برای نمادهای مشخص شده.
    اول schema جدید (current_prices + symbols) را امتحان می‌کند،
    در غیر این صورت از schema قدیم (prices + currencies) استفاده می‌کند.

    Returns:
        Dict[str, float]: {symbol: price_usd}
    """
    from sqlalchemy import text
    prices = {}

    if not symbols:
        return prices

    # New schema: current_prices + symbols
    # NOTE: Using parameterized bind params to prevent SQL injection
    try:
        placeholders = ",".join([f":sym_{i}" for i in range(len(symbols))])
        params = {f"sym_{i}": s for i, s in enumerate(symbols)}
        result = session.execute(text(f"""
            SELECT s.symbol, cp.price
            FROM symbols s
            INNER JOIN current_prices cp ON s.id = cp.symbol_id
            WHERE s.symbol IN ({placeholders})
        """), params)
        for row in result:
            prices[row[0].upper()] = float(row[1])

        if prices:
            logger.debug(f"Price alerts: got {len(prices)} prices from new schema")
            return prices
    except Exception as e:
        logger.debug(f"Price alerts: new schema not available: {e}")

    # Fallback: old schema (prices + currencies)
    try:
        placeholders = ",".join([f":sym_{i}" for i in range(len(symbols))])
        params = {f"sym_{i}": s for i, s in enumerate(symbols)}
        result = session.execute(text(f"""
            SELECT c.Symbol, p.price
            FROM prices p
            INNER JOIN currencies c ON p.crypto_id = c.CurrencyID
            WHERE c.Symbol IN ({placeholders})
              AND p.currency = 'USD'
              AND p.is_historical = 0
              AND p.last_updated = (
                  SELECT MAX(p2.last_updated)
                  FROM prices p2
                  WHERE p2.crypto_id = p.crypto_id
                    AND p2.currency = 'USD'
                    AND p2.is_historical = 0
              )
        """), params)
        for row in result:
            prices[row[0].upper()] = float(row[1])

        logger.debug(f"Price alerts: got {len(prices)} prices from old schema")
    except Exception as e:
        logger.debug(f"Price alerts: old schema query failed: {e}")

    return prices


def _check_price_alerts():
    """
    بررسی دوره‌ای هشدارهای قیمتی همه کاربران (هر ۱۰ دقیقه).

    از دو منبع می‌خواند:
      1) جدول جدید price_alerts (پشتیبانی از درصدی و قیمتی)
      2) جدول قدیمی settings (backward compatibility)

    رفتار:
      - هشدارهای قیمتی (above/below): یک‌بار مصرف → بعد از فعال شدن حذف می‌شوند
      - هشدارهای درصدی (percent_up/down): چندبار مصرف → reference_price آپدیت می‌شود
    """
    from sqlalchemy import text

    try:
        session = _get_session()
        try:
            # ============================================================
            # 1. Read alerts from BOTH tables
            # ============================================================
            user_alerts: Dict[str, list] = {}
            all_symbols: set = set()

            # ── 1a. New price_alerts table ──
            try:
                rows = session.execute(text("""
                    SELECT id, user_id, symbol, alert_type,
                           target_price, target_percent, reference_price
                    FROM price_alerts
                    WHERE is_active = 1
                """))
                for row in rows:
                    uid = row.user_id
                    symbol = row.symbol.upper()
                    alert_type = row.alert_type

                    alert = {
                        "source": "new",
                        "db_id": row.id,
                        "symbol": symbol,
                        "alert_type": alert_type,
                        "target_price": float(row.target_price) if row.target_price else None,
                        "target_percent": float(row.target_percent) if row.target_percent else None,
                        "reference_price": float(row.reference_price) if row.reference_price else None,
                    }

                    user_alerts.setdefault(uid, []).append(alert)
                    all_symbols.add(symbol)
            except Exception as e:
                logger.debug(f"Price alerts: new table query failed: {e}")

            # ── 1b. Legacy settings table ──
            try:
                legacy = session.execute(text("""
                    SELECT setting_key, setting_value FROM settings
                    WHERE setting_key LIKE 'price_alert:%'
                """))
                for row in legacy:
                    parts = row.setting_key.split(":")
                    if len(parts) < 4:
                        continue
                    uid = parts[1]
                    symbol = parts[2].upper()
                    alert_type = parts[3]

                    alert = {
                        "source": "legacy",
                        "key": row.setting_key,
                        "symbol": symbol,
                        "alert_type": alert_type,
                        "target_price": float(row.setting_value) if row.setting_value else 0,
                    }

                    user_alerts.setdefault(uid, []).append(alert)
                    all_symbols.add(symbol)
            except Exception:
                pass

            if not all_symbols:
                logger.debug("Price alerts: no active alerts found")
                return

            total_alerts = sum(len(v) for v in user_alerts.values())
            logger.info(f"Price alerts: checking {total_alerts} alerts "
                        f"for {len(user_alerts)} users, symbols={sorted(all_symbols)}")

            # ============================================================
            # 2. Get current prices
            # ============================================================
            current_prices = _get_current_prices(session, list(all_symbols))
            if not current_prices:
                logger.warning("Price alerts: no prices available from database")
                return

            # ============================================================
            # 3. Check each alert
            # ============================================================
            triggered_new_ids: list = []     # rows to DELETE from price_alerts
            reset_percent_alerts: list = []  # rows to UPDATE reference_price
            triggered_legacy_keys: list = [] # keys to DELETE from settings

            for user_id, alerts in user_alerts.items():
                for alert in alerts:
                    symbol = alert["symbol"]
                    current = current_prices.get(symbol)
                    if current is None:
                        continue

                    alert_type = alert["alert_type"]
                    is_triggered = False

                    if alert_type in ("above", "below"):
                        target = alert.get("target_price") or 0
                        if alert_type == "above" and current >= target:
                            is_triggered = True
                            PriceAlertNotifier.notify_price_alert(
                                user_id, symbol, current, target, "above"
                            )
                        elif alert_type == "below" and current <= target:
                            is_triggered = True
                            PriceAlertNotifier.notify_price_alert(
                                user_id, symbol, current, target, "below"
                            )

                        if is_triggered:
                            if alert.get("source") == "new":
                                triggered_new_ids.append(alert["db_id"])
                            else:
                                triggered_legacy_keys.append(alert["key"])

                    elif alert_type in ("percent_up", "percent_down"):
                        ref = alert.get("reference_price")
                        pct = alert.get("target_percent")
                        if ref is None or pct is None or ref <= 0:
                            continue

                        change_pct = ((current - ref) / ref) * 100

                        if alert_type == "percent_up" and change_pct >= pct:
                            is_triggered = True
                            PriceAlertNotifier.notify_price_alert(
                                user_id, symbol, current,
                                round(ref * (1 + pct / 100), 2),
                                "above",
                            )
                        elif alert_type == "percent_down" and change_pct <= -pct:
                            is_triggered = True
                            PriceAlertNotifier.notify_price_alert(
                                user_id, symbol, current,
                                round(ref * (1 - pct / 100), 2),
                                "below",
                            )

                        if is_triggered and alert.get("source") == "new":
                            # Recurring: update reference_price to current price
                            reset_percent_alerts.append((alert["db_id"], current))

            # ============================================================
            # 4. Apply changes
            # ============================================================
            changes_made = False

            # Delete triggered one-shot custom alerts (new table)
            if triggered_new_ids:
                for aid in triggered_new_ids:
                    session.execute(
                        text("DELETE FROM price_alerts WHERE id = :aid"),
                        {"aid": aid}
                    )
                changes_made = True
                logger.info(f"Price alerts: {len(triggered_new_ids)} custom alerts triggered and removed")

            # Reset reference_price for triggered percentage alerts (recurring)
            if reset_percent_alerts:
                for aid, new_ref in reset_percent_alerts:
                    session.execute(
                        text("UPDATE price_alerts SET reference_price = :ref WHERE id = :aid"),
                        {"ref": new_ref, "aid": aid}
                    )
                changes_made = True
                logger.info(f"Price alerts: {len(reset_percent_alerts)} percentage alerts reset to new reference")

            # Delete triggered legacy alerts (settings table)
            if triggered_legacy_keys:
                for key in triggered_legacy_keys:
                    session.execute(
                        text("DELETE FROM settings WHERE setting_key = :key"),
                        {"key": key}
                    )
                changes_made = True
                logger.info(f"Price alerts: {len(triggered_legacy_keys)} legacy alerts triggered and removed")

            if changes_made:
                session.commit()

        finally:
            session.close()
    except Exception as e:
        logger.error(f"Price alert checker error: {e}", exc_info=True)


# ============================================================
# Portfolio Summary (every 24 hours)
# ============================================================

def _send_daily_portfolio_summaries():
    """ارسال گزارش روزانه پورتفوی به همه کاربران."""
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        last_sent = _get_setting("portfolio_summary_last_sent", "")
        
        if last_sent == today:
            return  # Already sent today
        
        logger.info("Portfolio: sending daily summaries...")
        user_ids = get_all_user_ids()
        sent_count = 0
        
        for uid in user_ids:
            summary = calculate_portfolio_summary(uid)
            if summary:
                PriceAlertNotifier.notify_portfolio_summary(
                    user_id=uid,
                    total_balance_usd=summary["total_balance_usd"],
                    change_24h_percent=0,  # Would need historical data
                    change_7d_percent=0,
                    top_holding=summary.get("top_holding"),
                )
                sent_count += 1
        
        _set_setting("portfolio_summary_last_sent", today)
        logger.info(f"Portfolio: sent {sent_count} daily summaries")
        
    except Exception as e:
        logger.error(f"Portfolio summary error: {e}", exc_info=True)


# ============================================================
# Main Scheduler
# ============================================================

def _run_periodic(interval_s: int, name: str, func):
    """اجرای یک تابع به صورت دوره‌ای."""
    logger.info(f"Scheduler: starting {name} (every {interval_s}s)")
    while True:
        try:
            func()
        except Exception as e:
            logger.error(f"Scheduler/{name}: error: {e}")
        time.sleep(interval_s)


def start_scheduler():
    """شروع همه وظایف دوره‌ای."""
    
    # Gas checker: every 5 minutes
    t1 = threading.Thread(
        target=_run_periodic,
        args=(300, "GasCheck", _check_gas_prices),
        daemon=True,
        name="NotifScheduler-Gas",
    )
    t1.start()
    
    # Portfolio summary: every 24 hours (check every hour if it's time)
    def _hourly_portfolio_check():
        _send_daily_portfolio_summaries()
    
    t2 = threading.Thread(
        target=_run_periodic,
        args=(3600, "PortfolioSummary", _hourly_portfolio_check),
        daemon=True,
        name="NotifScheduler-Portfolio",
    )
    t2.start()
    
    # Price alert checker: every 10 minutes
    t3 = threading.Thread(
        target=_run_periodic,
        args=(600, "PriceAlert", _check_price_alerts),
        daemon=True,
        name="NotifScheduler-PriceAlert",
    )
    t3.start()

    logger.info("Notification scheduler started (gas=5min, price=10min, portfolio=1hr)")
    return [t1, t2, t3]


# Auto-start when module is imported in app context
_scheduler_threads: list = []
