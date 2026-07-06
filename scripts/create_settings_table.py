#!/usr/bin/env python3
import sys
sys.path.insert(0, '/opt/coinceeper/CC')
from database.settings import Settings
from database import engine
Settings.__table__.create(engine, checkfirst=True)
print("Settings table ready")
