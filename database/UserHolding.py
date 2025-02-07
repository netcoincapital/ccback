from sqlalchemy import Column, String, ForeignKey, BigInteger, TIMESTAMP, DECIMAL
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class UserHolding(Base):
    __tablename__ = 'UserHolding'

    HoldingID = Column(BigInteger, primary_key=True, autoincrement=True)
    UserID = Column(String(36), ForeignKey('Users.UserID'), nullable=False)
    CurrencyID = Column(String, ForeignKey('Currencies.CurrencyID'), nullable=False)
    Balance = Column(DECIMAL(20, 10), nullable=False)  # تغییر نام Amount به Balance
    UpdatedBalance = Column(DECIMAL(20, 10), nullable=True)  # اضافه کردن ستون جدید UpdatedBalance
    LastUpdated = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # رابطه با Users
    user = relationship('Users', back_populates='user_holdings')

    # رابطه با Currencies
    currency = relationship('Currencies', back_populates='user_holdings')

    def __repr__(self):
        return f"<UserHolding(HoldingID={self.HoldingID}, Balance={self.Balance}, UpdatedBalance={self.UpdatedBalance})>"