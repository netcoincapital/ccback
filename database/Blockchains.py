from sqlalchemy import Column, String, Integer, TIMESTAMP
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Blockchains(Base):
    __tablename__ = 'blockchains'

    BlockchainID = Column(Integer, primary_key=True, autoincrement=True)
    BlockchainName = Column(String(100), nullable=False, unique=True)
    Symbol = Column(String(50), nullable=False)
    ChainCode = Column(String(100), nullable=False)
    CreatedAt = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    UpdatedAt = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Fix back_populates relationship for Address
    addresses = relationship('Address', back_populates='blockchains')

    currencies = relationship('Currencies', back_populates='blockchains', foreign_keys='Currencies.BlockchainID')

    transfers = relationship('Transfers', back_populates='blockchain')

    def __repr__(self):
        return f"<Blockchains(BlockchainID={self.BlockchainID}, BlockchainName='{self.BlockchainName}')>"