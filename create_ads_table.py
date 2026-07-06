"""
Create the ads table and insert a test ad.

Usage:
  python create_ads_table.py

Or import and call create_ads_table() from your app context.
"""
import sys
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("create_ads_table")

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from database import engine, Base
from database.ads import Ads
from sqlalchemy import inspect
from datetime import datetime


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def create_ads_table():
    """Create the ads table and optionally insert a test ad."""
    if table_exists("ads"):
        logger.info("Table 'ads' already exists.")
    else:
        logger.info("Creating table 'ads'...")
        Ads.__table__.create(bind=engine, checkfirst=True)
        logger.info("Table 'ads' created successfully.")

    # Check again
    if table_exists("ads"):
        logger.info("Table 'ads' is now available.")
    else:
        logger.error("Failed to create table 'ads'!")
        return False

    return True


def insert_test_ad():
    """Insert a test ad record."""
    from database import SessionLocal

    session = SessionLocal()
    try:
        # Check if there's already data
        count = session.query(Ads).count()
        if count > 0:
            logger.info(f"Table already has {count} ad(s). Skipping test insert.")
            return True

        ad = Ads(
            title="GOLDEN RATIO SYSTEM",
            image_url="/uploads/ads/b4a40b0d4cd440a58730c1814ad39dd4.png",
            backlink="https://coinceeper.com",
            short_desc="Sistema ratio golden",
            is_active=True,
            start_date=datetime.now(),
            end_date=None,
        )
        session.add(ad)
        session.commit()
        logger.info(f"Test ad inserted with id={ad.id}")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Error inserting test ad: {str(e)}")
        return False
    finally:
        session.close()


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Creating ads table...")
    logger.info("=" * 50)

    if create_ads_table():
        insert_test_ad()
        logger.info("\nDone! Now try GET /api/ads/ again.")
    else:
        logger.error("\nFailed to set up ads table. Check database connection.")
        sys.exit(1)
