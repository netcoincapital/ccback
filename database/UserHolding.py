from sqlalchemy import Column, String, ForeignKey, BigInteger, TIMESTAMP, Text, DECIMAL, Boolean, JSON, func
from sqlalchemy.orm import relationship
from .base import Base

class UserHolding(Base):
    __tablename__ = 'UserHolding'

    HoldingID = Column(BigInteger, primary_key=True, autoincrement=True)
    
    UserID = Column(String(36), ForeignKey('Users.UserID'), nullable=False)
    CurrencyID = Column(String(10), ForeignKey('Currencies.CurrencyID'), nullable=False)
    
    Balance = Column(DECIMAL(38, 18), nullable=False, default=0)
    Symbol = Column(String(20), nullable=False)
    Blockchain = Column(String(50), nullable=False)
    IsToken = Column(Boolean, nullable=False, default=False)

    CreatedAt = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    UpdatedAt = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    LastUpdated = Column(TIMESTAMP, nullable=True)
    RawData = Column(JSON, nullable=True)

    # روابط
    user = relationship('Users', back_populates='user_holdings')
    currency = relationship('Currencies')

    def __repr__(self):
        return (
            f"<UserHolding(HoldingID={self.HoldingID}, UserID={self.UserID}, "
            f"CurrencyID={self.CurrencyID}, Balance={self.Balance}, Symbol={self.Symbol}, "
            f"Blockchain={self.Blockchain}, IsToken={self.IsToken})>"
        )
