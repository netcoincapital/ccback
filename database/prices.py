from sqlalchemy import Column, String, Integer, BigInteger, DECIMAL, DateTime, ForeignKey, UniqueConstraint, Index, func, Boolean
from sqlalchemy.orm import relationship
from .base import Base

class Price(Base):
    __tablename__ = 'prices'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    crypto_id = Column(String(10), ForeignKey('currencies.CurrencyID'), nullable=False)

    currency = Column(String(10), nullable=False, default='USD')
    price = Column(DECIMAL(20, 8), nullable=False)
    market_cap = Column(DECIMAL(30, 2), nullable=True)
    volume_24h = Column(DECIMAL(30, 2), nullable=True)
    change_1h = Column(DECIMAL(8, 2), nullable=True)
    change_24h = Column(DECIMAL(8, 2), nullable=True)
    change_7d = Column(DECIMAL(8, 2), nullable=True)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Historical data support
    is_historical = Column(Boolean, nullable=False, default=False)
    timestamp = Column(DateTime, nullable=True)  # For historical records
    
    __table_args__ = (
        # Fixed constraint: only for non-historical records to avoid conflicts
        UniqueConstraint('crypto_id', 'currency', 'timestamp', name='unique_crypto_currency_timestamp'),
        # Conditional unique constraint: only for current prices (is_historical=false)
        # Note: This constraint was causing issues and has been removed
        # UniqueConstraint('crypto_id', 'currency', name='unique_crypto_currency'),
        Index('crypto_id_idx', 'crypto_id'),
        Index('timestamp_idx', 'timestamp'),
        Index('historical_idx', 'is_historical'),
        Index('current_price_idx', 'crypto_id', 'currency', 'is_historical'),
    )

    currency_ref = relationship('Currencies', back_populates='prices')

    def __repr__(self):
        return f"<Price(id={self.id}, crypto_id='{self.crypto_id}', price={self.price}, historical={self.is_historical})>"
    
    def to_dict(self):
        """Convert price record to dictionary"""
        return {
            'id': self.id,
            'crypto_id': self.crypto_id,
            'currency': self.currency,
            'price': float(self.price),
            'market_cap': float(self.market_cap) if self.market_cap else None,
            'volume_24h': float(self.volume_24h) if self.volume_24h else None,
            'change_1h': float(self.change_1h) if self.change_1h else None,
            'change_24h': float(self.change_24h) if self.change_24h else None,
            'change_7d': float(self.change_7d) if self.change_7d else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'is_historical': self.is_historical,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
    
    @classmethod
    def get_historical_data(cls, session, crypto_id, currency='USD', time_start=None, time_end=None):
        """Helper method to get historical data for a specific currency"""
        query = session.query(cls).filter_by(
            crypto_id=str(crypto_id),
            currency=currency,
            is_historical=True
        )
        
        if time_start:
            query = query.filter(cls.timestamp >= time_start)
        if time_end:
            query = query.filter(cls.timestamp <= time_end)
            
        return query.order_by(cls.timestamp).all()
    
    @classmethod
    def get_current_price(cls, session, crypto_id, currency='USD'):
        """Helper method to get current price for a specific currency"""
        return session.query(cls).filter_by(
            crypto_id=str(crypto_id),
            currency=currency,
            is_historical=False
        ).first()
