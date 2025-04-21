# database/BalanceUpdateLog.py
from sqlalchemy import Column, String, Integer, DateTime, Float, UniqueConstraint
from sqlalchemy.sql import func
from .base import Base

class BalanceUpdateLog(Base):
    """
    جدول ثبت وقایع به‌روزرسانی موجودی
    برای جلوگیری از پردازش دوباره تراکنش‌ها استفاده می‌شود
    """
    __tablename__ = 'balance_update_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    wallet_id = Column(String(50), nullable=False, index=True)
    tx_id = Column(String(255), nullable=False, index=True)
    direction = Column(String(20), nullable=False)  # inbound یا outbound
    amount = Column(String(50), nullable=False)
    token_symbol = Column(String(50), nullable=False)
    blockchain = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    
    # اضافه کردن محدودیت یکتا برای جلوگیری از پردازش مجدد تراکنش
    __table_args__ = (
        UniqueConstraint('wallet_id', 'tx_id', 'direction', name='uq_wallet_tx_direction'),
    )
    
    def __repr__(self):
        return f"<BalanceUpdateLog(id={self.id}, wallet_id={self.wallet_id}, tx_id={self.tx_id})>" 