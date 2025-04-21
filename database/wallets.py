from sqlalchemy import Column, String, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base
import uuid

class Wallets(Base):
    __tablename__ = 'wallets'

    WalletID = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    UserID = Column(String(36), ForeignKey('users.UserID', ondelete='CASCADE'), nullable=False)
    IsMultiSig = Column(Boolean, default=False, nullable=False)
    RequiredSignatures = Column(String(10), nullable=False)
    CreatedAt = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False)
    UpdatedAt = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship('Users', back_populates='wallets')
    addresses = relationship('Address', back_populates='wallets')
    transfers = relationship('Transfers', back_populates='wallet')

    def __repr__(self):
        return f"<Wallet(WalletID={self.WalletID}, UserID={self.UserID}, IsMultiSig={self.IsMultiSig}, RequiredSignatures='{self.RequiredSignatures}')>"
