from sqlalchemy import Column, String, Integer, ForeignKey, TIMESTAMP, TEXT, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Address(Base):
    __tablename__ = 'address'

    AddressID = Column(Integer, primary_key=True, autoincrement=True)
    WalletID = Column(String(50), ForeignKey('wallets.WalletID'), nullable=False)
    BlockchainID = Column(Integer, ForeignKey('blockchains.BlockchainID'), nullable=False)
    PublicAddress = Column(String(255), nullable=False)
    PrivateKey = Column(TEXT, nullable=True)
    PhraseKey = Column(TEXT, nullable=True)
    CreatedAt = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('ix_public_address', 'PublicAddress'),
    )

    wallets = relationship('Wallets', back_populates='addresses', foreign_keys=[WalletID])
    blockchains = relationship('Blockchains', back_populates='addresses', foreign_keys=[BlockchainID])
    transfers = relationship('Transfers', back_populates='address')

    def __repr__(self):
        return f"<Address(AddressID={self.AddressID}, PublicAddress='{self.PublicAddress}')>"
