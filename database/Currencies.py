from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Currencies(Base):
    __tablename__ = 'Currencies'

    CurrencyID = Column(String, primary_key=True)
    CurrencyName = Column(String(255), nullable=False)
    Icon = Column(String(255), nullable=False)
    Symbol = Column(String(50), nullable=False)
    BlockchainID = Column(Integer, ForeignKey('Blockchains.BlockchainID'), nullable=False)
    DecimalPlaces = Column(Integer, nullable=False)
    IsToken = Column(Boolean, nullable=False, default=False)
    SmartContractAddress = Column(String(255), nullable=True)
    CreatedAt = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    UpdatedAt = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # رابطه با Blockchains
    blockchains = relationship('Blockchains', back_populates='currencies')

    # رابطه با UserHolding
    user_holdings = relationship('UserHolding', back_populates='currency')

    def __repr__(self):
        return f"<Currencies(CurrencyID={self.CurrencyID}, CurrencyName='{self.CurrencyName}')>"
