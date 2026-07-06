from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text
from database import engine, Currencies
from database.prices import Price
from utils.logging_config import get_logger
from datetime import timedelta

logger = get_logger(__file__)

# کش سبک برای جلوگیری از reflection مکرر روی هر درخواست
_schema_cache: Optional[Dict[str, Any]] = None


def _get_schema_flags():
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache
    from sqlalchemy import inspect as sqla_inspect

    inspector = sqla_inspect(engine)
    table_names = {t.lower() for t in inspector.get_table_names()}
    _schema_cache = {
        "has_new": "current_prices" in table_names,
        "has_old": "prices" in table_names,
    }
    return _schema_cache


class PriceDbService:
    """سرویس مدیریت قیمت‌ها در دیتابیس"""

    @staticmethod
    def get_prices(currency_ids, fiat_currencies):
        """
        دريافت قيمت‌ها از جداول جدید (current_prices + fiat_rates)
        - قیمت‌ها فقط در USD ذخیره شده‌اند
        - تبدیل به سایر ارزها با استفاده از fiat_rates
        """
        logger.info(f"Fetching prices for {len(currency_ids)} currencies in {len(fiat_currencies)} fiats")
        session = Session(bind=engine)
        try:
            flags = _get_schema_flags()
            has_new_schema = flags["has_new"]
            has_old_schema = flags["has_old"]

            string_ids = [str(cid) for cid in currency_ids]
            
            out = {cid: {} for cid in currency_ids}

            for cid in currency_ids:
                scid = str(cid)

                price_data = None
                if has_new_schema:
                    price_data = session.execute(text("""
                        SELECT 
                            cp.price,
                            cp.market_cap,
                            cp.volume_24h,
                            cp.change_1h,
                            cp.change_24h,
                            cp.change_7d,
                            cp.last_updated
                        FROM current_prices cp
                        WHERE cp.symbol_id = :symbol_id
                    """), {"symbol_id": scid}).first()
                
                if not price_data:
                    # Fallback: old prices table (crypto_id + fiat currency)
                    if has_old_schema:
                        for fiat in fiat_currencies:
                            old_row = session.execute(
                                text(
                                    """
                                    SELECT
                                        p.price,
                                        p.market_cap,
                                        p.volume_24h,
                                        p.change_1h,
                                        p.change_24h,
                                        p.change_7d,
                                        COALESCE(p.last_updated, p.timestamp) AS updated_at
                                    FROM prices p
                                    WHERE p.crypto_id = :crypto_id
                                      AND p.currency = :fiat
                                    ORDER BY p.id DESC
                                    LIMIT 1
                                    """
                                ),
                                {"crypto_id": scid, "fiat": fiat},
                            ).first()
                            if old_row:
                                out[cid][fiat] = {
                                    "price": float(old_row[0]) if old_row[0] is not None else 0.0,
                                    "market_cap": float(old_row[1]) if old_row[1] is not None else None,
                                    "volume_24h": float(old_row[2]) if old_row[2] is not None else None,
                                    "change_1h": float(old_row[3]) if old_row[3] is not None else None,
                                    "change_24h": float(old_row[4]) if old_row[4] is not None else 0.0,
                                    "change_7d": float(old_row[5]) if old_row[5] is not None else None,
                                    "updated_at": old_row[6],
                                }
                            else:
                                out[cid][fiat] = {
                                    "price": 0.0,
                                    "market_cap": None,
                                    "volume_24h": None,
                                    "change_1h": None,
                                    "change_24h": 0.0,
                                    "change_7d": None,
                                    "updated_at": None,
                                }
                        continue

                    for fiat in fiat_currencies:
                        out[cid][fiat] = {
                            "price": 0.0,
                            "market_cap": None,
                            "volume_24h": None,
                            "change_1h": None,
                            "change_24h": 0.0,
                            "change_7d": None,
                            "updated_at": None,
                        }
                    continue

                price_usd = float(price_data[0]) if price_data[0] else 0.0

                for fiat in fiat_currencies:
                    fiat_rate_row = session.execute(
                        text("SELECT rate FROM fiat_rates WHERE quote_currency = :fiat"),
                        {"fiat": fiat},
                    ).first()

                    fiat_rate = float(fiat_rate_row[0]) if fiat_rate_row else 1.0

                    out[cid][fiat] = {
                        "price": price_usd * fiat_rate,
                        "market_cap": float(price_data[1]) * fiat_rate if price_data[1] else None,
                        "volume_24h": float(price_data[2]) * fiat_rate if price_data[2] else None,
                        "change_1h": float(price_data[3]) if price_data[3] else None,
                        "change_24h": float(price_data[4]) if price_data[4] else 0.0,
                        "change_7d": float(price_data[5]) if price_data[5] else None,
                        "updated_at": price_data[6],
                    }

            return out

        except Exception as e:
            logger.error(f"Error fetching prices: {e}", exc_info=True)
            return {}
        finally:
            session.close()

    @staticmethod
    def update_prices(currency_ids=None, fiat_currencies=None):
        """
        Update prices for specified currencies using CurrencyPriceService
        
        Args:
            currency_ids (list): List of currency IDs to update (if None, update all)
            fiat_currencies (list): List of fiat currencies (if None, use default)
            
        Returns:
            dict: Result with success status and statistics
        """
        try:
            import time
            from Currencies.currency_price_service import CurrencyPriceService, fiat_symbols
            
            start_time = time.time()
            logger.info("Starting PriceDbService.update_prices")
            
            # Initialize price service
            price_service = CurrencyPriceService()
            
            # Set default fiat currencies if not provided
            if fiat_currencies is None:
                fiat_currencies = ["USD"]
            
            # Get all currencies if specific ones not provided
            if currency_ids is None:
                session = Session(bind=engine)
                try:
                    currencies = session.query(Currencies).filter(Currencies.CMC_ID.isnot(None)).all()
                    currency_ids = [c.CurrencyID for c in currencies]
                    logger.info(f"No specific currencies provided, updating all {len(currency_ids)} currencies")
                finally:
                    session.close()
            
            if not currency_ids:
                return {
                    "success": False,
                    "message": "No currencies found to update",
                    "currencies_count": 0,
                    "fiats_count": 0,
                    "elapsed_time": 0
                }
            
            # Use CurrencyPriceService to update prices
            result = price_service.update_prices(currency_ids, fiat_currencies)
            
            elapsed_time = time.time() - start_time
            
            if result:
                logger.info(f"Price update completed successfully in {elapsed_time:.2f} seconds")
                return {
                    "success": True,
                    "message": "Prices updated successfully",
                    "currencies_count": len(currency_ids),
                    "fiats_count": len(fiat_currencies),
                    "elapsed_time": elapsed_time
                }
            else:
                logger.error("Price update failed")
                return {
                    "success": False,
                    "message": "Price update failed",
                    "currencies_count": len(currency_ids),
                    "fiats_count": len(fiat_currencies),
                    "elapsed_time": elapsed_time
                }
                
        except Exception as e:
            logger.error(f"Error in PriceDbService.update_prices: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "currencies_count": 0,
                "fiats_count": 0,
                "elapsed_time": 0
            }

    @staticmethod
    def get_price_stats():
        """
        آمار کلی جداول قیمت برای endpoint /api/price-stats
        اگر جداول کامل نباشند، مقادیر امن برمی‌گردد تا 500 نشود.
        """
        from sqlalchemy import inspect as sqla_inspect, text

        empty = {
            "total_tracked_currencies": 0,
            "currencies_with_price": 0,
            "latest_update": None,
            "up_to_date_percentage": 0.0,
        }
        try:
            insp = sqla_inspect(engine)
            try:
                raw_tables = insp.get_table_names()
            except Exception as e:
                logger.warning("get_table_names failed in get_price_stats: %s", e)
                return empty

            tset = {n.lower() for n in raw_tables}
            if "current_prices" not in tset:
                if "prices" not in tset:
                    return empty
                session = Session(bind=engine)
                try:
                    row = session.execute(
                        text("SELECT COUNT(*), MAX(COALESCE(last_updated, timestamp)) FROM prices")
                    ).first()
                    price_rows = int(row[0] or 0) if row else 0
                    latest = row[1] if row else None
                except Exception as e:
                    logger.warning("prices stats query failed: %s", e, exc_info=True)
                    return empty
                finally:
                    session.close()

                total = 0
                if "currencies" in tset:
                    session = Session(bind=engine)
                    try:
                        r = session.execute(
                            text("SELECT COUNT(*) FROM currencies WHERE CMC_ID IS NOT NULL")
                        ).scalar()
                        total = int(r or 0)
                    except Exception as e:
                        logger.warning("currencies count in get_price_stats: %s", e)
                    finally:
                        session.close()
                up_pct = 100.0 if total == 0 and price_rows > 0 else 100.0 * min(1.0, price_rows / max(total, 1))
                return {
                    "total_tracked_currencies": total,
                    "currencies_with_price": price_rows,
                    "latest_update": latest,
                    "up_to_date_percentage": up_pct,
                }

            session = Session(bind=engine)
            try:
                row = session.execute(
                    text("SELECT COUNT(*), MAX(last_updated) FROM current_prices")
                ).first()
                price_rows = int(row[0] or 0) if row else 0
                latest = row[1] if row else None
            except Exception as e:
                logger.warning("current_prices stats query failed: %s", e, exc_info=True)
                return empty
            finally:
                session.close()

            total = 0
            if "currencies" in tset:
                session = Session(bind=engine)
                try:
                    r = session.execute(
                        text(
                            "SELECT COUNT(*) FROM currencies WHERE CMC_ID IS NOT NULL"
                        )
                    ).scalar()
                    total = int(r or 0)
                except Exception as e:
                    logger.warning("currencies count in get_price_stats: %s", e)
                finally:
                    session.close()
            if total == 0 and price_rows > 0:
                up_pct = 100.0
            else:
                up_pct = 100.0 * min(1.0, price_rows / max(total, 1))

            return {
                "total_tracked_currencies": total,
                "currencies_with_price": price_rows,
                "latest_update": latest,
                "up_to_date_percentage": up_pct,
            }
        except Exception as e:
            logger.error("get_price_stats failed: %s", e, exc_info=True)
            return empty
