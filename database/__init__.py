# database/__init__.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .base import Base
from .users import Users
from .wallets import Wallets
from .Address import Address
from .Blockchains import Blockchains
from .Currencies import Currencies
from .UserHolding import UserHolding
from .Transfers import Transfers
from .prices import Price
from .BalanceUpdateLog import BalanceUpdateLog
from .UserDevices import UserDevices
from .ads import Ads
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load env vars directly
load_dotenv()

# Build database URL from individual components with proper encoding
DB_USER = os.getenv('DB_USER', 'coincee')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_NAME = os.getenv('DB_NAME', 'coincee')
DB_DRIVER = os.getenv('DB_DRIVER', 'pymysql')

if DB_PASSWORD:
    DB_PASSWORD = quote_plus(DB_PASSWORD)

DATABASE_URL = f"mysql+{DB_DRIVER}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

# ایجاد موتور دیتابیس
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=30,
    max_overflow=60,
    pool_timeout=120,
    pool_recycle=1800,
)

# ایجاد یک Session برای مدیریت تراکنش‌ها
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# تابعی برای ساخت جداول در دیتابیس
def init_db():
    Base.metadata.create_all(bind=engine)

"""Database package initialization."""
