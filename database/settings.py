from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from Database.base import Base

class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(100), unique=True, nullable=False)
    setting_value = Column(Text, nullable=True)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<Settings(id={self.id}, key='{self.setting_key}')>" 