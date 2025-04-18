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
    CMC_ID = Column(Integer, nullable=True)

    prices = relationship('Price', back_populates='currency_ref')
    blockchains = relationship('Blockchains', back_populates='currencies')

    def __repr__(self):
        return f"<Currencies(CurrencyID={self.CurrencyID}, CurrencyName='{self.CurrencyName}')>"

    def to_dict(self):
        return {
            'CurrencyID': self.CurrencyID,
            'CurrencyName': self.CurrencyName,
            'Symbol': self.Symbol,
            'Icon': self.Icon,
            'BlockchainID': self.BlockchainID,
            'DecimalPlaces': self.DecimalPlaces,
            'IsToken': self.IsToken,
            'SmartContractAddress': self.SmartContractAddress,
            'CMC_ID': self.CMC_ID  # اضافه کردن برای سریال‌سازی
        }
