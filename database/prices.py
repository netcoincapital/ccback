from sqlalchemy import Column, String, Integer, BigInteger, DECIMAL, DateTime, ForeignKey, UniqueConstraint, Index, func
from sqlalchemy.orm import relationship
from .base import Base

class Price(Base):
    __tablename__ = 'prices'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    crypto_id = Column(String(10), ForeignKey('Currencies.CurrencyID'), nullable=False)

    currency = Column(String(10), nullable=False, default='USD')
    price = Column(DECIMAL(20, 8), nullable=False)
    market_cap = Column(DECIMAL(30, 2), nullable=True)
    volume_24h = Column(DECIMAL(30, 2), nullable=True)
    change_1h = Column(DECIMAL(8, 2), nullable=True)
    change_24h = Column(DECIMAL(8, 2), nullable=True)
    change_7d = Column(DECIMAL(8, 2), nullable=True)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint('crypto_id', 'currency', name='unique_crypto_currency'),
        Index('crypto_id_idx', 'crypto_id'),
    )

    currency_ref = relationship('Currencies', back_populates='prices')

    def __repr__(self):
        return f"<Price(id={self.id}, crypto_id='{self.crypto_id}', price={self.price})>"
