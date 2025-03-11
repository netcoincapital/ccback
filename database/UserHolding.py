from sqlalchemy import Column, String, ForeignKey, BigInteger, TIMESTAMP, Text, DECIMAL
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class UserHolding(Base):
    __tablename__ = 'UserHolding'

    HoldingID = Column(BigInteger, primary_key=True, autoincrement=True)
    UserID = Column(String(36), ForeignKey('Users.UserID'), nullable=False)
    Balance = Column(DECIMAL(20,10), nullable=True)  # مقدار عددی و قابل null
    Tokens = Column(Text().with_variant(Text, 'mysql').with_variant(Text, 'postgresql'), nullable=True)  # ذخیره‌ی رشته‌ای مانند "ETH : 1 , TRX : 200"
    LastUpdated = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # رابطه با Users
    user = relationship('Users', back_populates='user_holdings')

    def __repr__(self):
        return f"<UserHolding(HoldingID={self.HoldingID}, Balance={self.Balance}, Tokens={self.Tokens})>"
