import sys
sys.path.insert(0, '/opt/coinceeper/CC')
from database import SessionLocal
from datetime import datetime, timezone
from sqlalchemy import text

s = SessionLocal()
try:
    sql = """INSERT INTO currencies (CurrencyID, CurrencyName, Symbol, Icon, BlockchainID, DecimalPlaces, IsToken, SmartContractAddress, CreatedAt, UpdatedAt)
VALUES (:cid, :cname, :sym, :icon, :bid, :dec, :token, :contract, :now, :now)"""
    s.execute(text(sql), {
        'cid': '9541',
        'cname': 'Coinceeper',
        'sym': 'CC',
        'icon': 'https://coinceeper.com/CC/cryptoicons/CC.png',
        'bid': 5,
        'dec': 18,
        'token': 1,
        'contract': '0x7C8cBA63741D92e4029Ef6775729F29F4Bc31691',
        'now': datetime.now(timezone.utc)
    })
    s.commit()
    print('CC token inserted successfully!')
    
    # Verify
    r = s.execute(text("SELECT CurrencyID, CurrencyName, Symbol, Icon, SmartContractAddress FROM currencies WHERE CurrencyID = '9541'")).fetchone()
    if r:
        print(f'Verified: ID={r[0]}, Name={r[1]}, Symbol={r[2]}, Icon={r[3]}, Contract={r[4]}')
    else:
        print('ERROR: Not found after insert!')
finally:
    s.close()
