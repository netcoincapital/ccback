# -*- coding: utf-8 -*-
"""
Bootstrap NCC historical data for 2 months
Generates daily + hourly candles from $0.10 to $0.22
and calculates change_1h / change_24h / change_7d
"""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from dotenv import load_dotenv
from sqlalchemy.dialects.mysql import insert

# بارگذاری env
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# افزودن مسیر پروژه به sys.path
PROJECT_ROOT = BASE_DIR
REPO_ROOT = os.path.dirname(PROJECT_ROOT)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# --- Session و مدل‌ها ---
from CC.database.base import SessionLocal
from CC.database.prices import Price
from CC.database.Currencies import Currencies

# نرخ تبدیل ساده
FIAT_CURRENCIES = {
    "USD": 1.0, "EUR": 0.92, "GBP": 0.78, "CAD": 1.37, "AUD": 1.50,
    "CNY": 7.11, "JPY": 145.0, "KRW": 1330.0, "RUB": 89.0, "TRY": 32.0,
    "IQD": 1309.0, "SAR": 3.75, "KWD": 0.31, "BHD": 0.376, "INR": 83.0,
}


def calculate_fiat_price(usd_price: float, fiat: str) -> float:
    return usd_price * (FIAT_CURRENCIES.get(fiat, 1.0) / FIAT_CURRENCIES["USD"])


def get_ncc_ids(session):
    ids = []
    candidates = session.query(Currencies).filter(Currencies.Symbol == "NCC").all()
    for c in candidates:
        if hasattr(c, "cmc_id") and c.cmc_id:
            ids.append(str(c.cmc_id))
        elif hasattr(c, "CurrencyID"):
            ids.append(str(c.CurrencyID))
    return ids


def _pct(cur, prev):
    if not prev or prev == 0:
        return Decimal("0.0")
    return Decimal(str(((cur / prev) - 1.0) * 100.0))


def bootstrap():
    session = SessionLocal()
    try:
        ncc_ids = get_ncc_ids(session)
        if not ncc_ids:
            print("⚠️ No NCC found in Currencies table")
            return

        start_price = 0.10
        end_price = 0.22
        days = 60
        step = (end_price - start_price) / (days - 1)

        today = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

        for day in range(days):
            usd_price = start_price + step * day
            base_ts = today - timedelta(days=(days - 1 - day))

            market_cap = usd_price * 100_000_000
            volume = 400_000

            for crypto_id in ncc_ids:
                for fiat in FIAT_CURRENCIES.keys():
                    fiat_price = calculate_fiat_price(usd_price, fiat)

                    # رکوردهای ۲۴ ساعت
                    for h in range(24):
                        ts = base_ts.replace(hour=0) + timedelta(hours=h)

                        # پیدا کردن رکوردهای قبلی
                        prev_1h = session.query(Price).filter_by(
                            crypto_id=str(crypto_id),
                            currency=fiat,
                            timestamp=ts - timedelta(hours=1)
                        ).first()

                        prev_24h = session.query(Price).filter_by(
                            crypto_id=str(crypto_id),
                            currency=fiat,
                            timestamp=ts - timedelta(hours=24)
                        ).first()

                        prev_7d = session.query(Price).filter_by(
                            crypto_id=str(crypto_id),
                            currency=fiat,
                            timestamp=ts - timedelta(days=7)
                        ).first()

                        row = Price(
                            crypto_id=str(crypto_id),
                            currency=fiat,
                            price=Decimal(str(fiat_price)),
                            market_cap=Decimal(str(market_cap)),
                            volume_24h=Decimal(str(volume)),
                            change_1h=_pct(fiat_price, float(prev_1h.price)) if prev_1h else Decimal("0.0"),
                            change_24h=_pct(fiat_price, float(prev_24h.price)) if prev_24h else Decimal("0.0"),
                            change_7d=_pct(fiat_price, float(prev_7d.price)) if prev_7d else Decimal("0.0"),
                            last_updated=ts,
                            timestamp=ts,
                            is_historical=1
                        )
                        session.add(row)

        session.commit()
        print(f"✅ Bootstrapped {days} days of daily+hourly history for NCC")

    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    bootstrap()
