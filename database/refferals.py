# database/refferals.py
from sqlalchemy import Column, String, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base
import uuid

class Refferals(Base):
    __tablename__ = 'Refferals'

    RefferalID = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    UserID = Column(String(36), ForeignKey('Users.UserID', ondelete='CASCADE'), nullable=False)
    Refferal_UserID = Column(String(50), nullable=False)
    Refferal_Code = Column(String(50), nullable=False, unique=True)
    Refferal_Date = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)

    # رابطه با Users
    user = relationship('Users', back_populates='refferals')

    def __repr__(self):
        return f"<Refferal(RefferalID={self.RefferalID}, UserID='{self.UserID}', Refferal_Code='{self.Refferal_Code}', Refferal_UserID='{self.Refferal_UserID}')>"
