import sys
sys.path.insert(0, '/opt/coinceeper/CC')
from database import SessionLocal
from sqlalchemy import text
s = SessionLocal()
try:
    r = s.execute(text('SELECT MAX(CAST(CurrencyID AS UNSIGNED)) FROM currencies')).fetchone()[0]
    print('MaxID:' + str(r))
    r = s.execute(text("SELECT BlockchainID FROM blockchains WHERE ChainCode = 'MATIC'")).fetchone()[0]
    print('PolygonID:' + str(r))
    r = s.execute(text("SELECT COUNT(1) FROM currencies WHERE Symbol = 'CC'")).fetchone()[0]
    print('CCexists:' + str(r))
finally:
    s.close()
