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
from config import DATABASE_URL

# ایجاد موتور دیتابیس
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# ایجاد یک Session برای مدیریت تراکنش‌ها
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# تابعی برای ساخت جداول در دیتابیس
def init_db():
    Base.metadata.create_all(bind=engine)
