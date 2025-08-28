from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from database import engine, Currencies
from database.prices import Price
from utils.logging_config import get_logger
from datetime import timedelta

logger = get_logger(__file__)

class PriceDbService:
    """سرویس مدیریت قیمت‌ها در دیتابیس"""

    @staticmethod
    def get_prices(currency_ids, fiat_currencies):
        """
        دريافت جديدترين قيمت هر (crypto_id, currency) از جدول prices.
        - هميشه آخرين ركورد بر اساس COALESCE(timestamp, last_updated) برگردانده می‌شود.
        - اگر change_24h نال بود، از داده‌ی ۲۴ ساعت قبل محاسبه می‌گردد.
        """
        logger.info(f"Fetching prices for {len(currency_ids)} currencies in {len(fiat_currencies)} fiats")
        session = Session(bind=engine)
        try:
            string_ids = [str(cid) for cid in currency_ids]

            # شاخص زمان برای مرتب‌سازی/انتخاب آخرین رکورد
            ts_expr = func.coalesce(Price.timestamp, Price.last_updated)

            # ساب‌کوئری: آخرین زمان هر (crypto_id, currency)
            latest_sub = (
                session.query(
                    Price.crypto_id.label("cid"),
                    Price.currency.label("fiat"),
                    func.max(ts_expr).label("mx_ts"),
                )
                .filter(Price.crypto_id.in_(string_ids))
                .filter(Price.currency.in_(fiat_currencies))
                .group_by(Price.crypto_id, Price.currency)
                .subquery()
            )

            # جوین با جدول prices روی بیشینه‌ی زمان محاسبه‌شده
            latest_rows = (
                session.query(Price)
                .join(
                    latest_sub,
                    and_(
                        Price.crypto_id == latest_sub.c.cid,
                        Price.currency == latest_sub.c.fiat,
                        func.coalesce(Price.timestamp, Price.last_updated) == latest_sub.c.mx_ts,
                    ),
                )
                .all()
            )

            # نگاشت سریع برای دسترسی O(1)
            pick = {(r.crypto_id, r.currency): r for r in latest_rows}

            # خروجی
            out = {cid: {} for cid in currency_ids}

            for cid in currency_ids:
                scid = str(cid)
                for fiat in fiat_currencies:
                    rec = pick.get((scid, fiat))
                    if not rec:
                        out[cid][fiat] = {"price": 0.0, "change_24h": 0.0, "updated_at": None}
                        continue

                    price_val = float(rec.price) if rec.price is not None else 0.0

                    # اگر change_24h ذخیره‌شده موجود بود همان را بده، وگرنه محاسبه کن
                    if rec.change_24h is not None:
                        ch24 = float(rec.change_24h)
                    else:
                        # محاسبه‌ی دستی: نسبت (قیمت فعلی - قیمت 24h قبل) / قیمت 24h قبل * 100
                        anchor_dt = rec.timestamp or rec.last_updated
                        prev_row = (
                            session.query(Price.price)
                            .filter(
                                Price.crypto_id == scid,
                                Price.currency == fiat,
                                Price.is_historical.is_(True),
                                Price.timestamp <= anchor_dt - timedelta(hours=24),
                            )
                            .order_by(Price.timestamp.desc())
                            .first()
                        )
                        if prev_row and prev_row[0] not in (None, 0):
                            prev_price = float(prev_row[0])
                            ch24 = ((price_val - prev_price) / prev_price) * 100.0
                        else:
                            ch24 = 0.0

                    out[cid][fiat] = {
                        "price": price_val,
                        "change_24h": ch24,
                        "updated_at": rec.timestamp or rec.last_updated,
                    }

            return out

        except Exception as e:
            logger.error(f"Error fetching prices: {e}", exc_info=True)
            return {}
        finally:
            session.close()
