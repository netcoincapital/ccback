from sqlalchemy import Column, String, Integer, ForeignKey, TIMESTAMP, TEXT, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

class Address(Base):
    __tablename__ = 'Address'

    AddressID = Column(Integer, primary_key=True, autoincrement=True)
    WalletID = Column(String(50), ForeignKey('Wallets.WalletID'), nullable=False)
    BlockchainID = Column(Integer, ForeignKey('Blockchains.BlockchainID'), nullable=False)
    PublicAddress = Column(String(255), nullable=False)
    PrivateKey = Column(TEXT, nullable=True)
    PhraseKey = Column(TEXT, nullable=True)
    CreatedAt = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('ix_public_address', 'PublicAddress'),
    )

    wallets = relationship('Wallets', back_populates='addresses')
    blockchains = relationship('Blockchains', back_populates='addresses')

    def __repr__(self):
        return f"<Address(AddressID={self.AddressID}, PublicAddress='{self.PublicAddress}')>"
