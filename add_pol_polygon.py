"""
Add POL (Polygon) record to the currencies table on Polygon blockchain.
Also display existing MATIC and POL records for reference.
"""
import sys
sys.path.insert(0, '/opt/coinceeper/CC')

from database import SessionLocal
from sqlalchemy import text

session = SessionLocal()
try:
    # 1. Show existing records for reference
    print("=== Existing MATIC & POL records ===")
    rows = session.execute(text("""
        SELECT c.CurrencyID, c.CurrencyName, c.Symbol, c.BlockchainID, 
               c.DecimalPlaces, c.IsToken, c.SmartContractAddress, c.Icon,
               b.BlockchainName
        FROM currencies c
        JOIN blockchains b ON c.BlockchainID = b.BlockchainID
        WHERE c.CurrencyID IN ('8518', '8526')
    """)).fetchall()
    
    for row in rows:
        print(f"  ID={row[0]}, Name={row[1]}, Symbol={row[2]}, Chain={row[8]}, "
              f"Dec={row[4]}, Token={row[5]}, Contract={row[6]}, Icon={row[7]}")
    
    # 2. Get Polygon BlockchainID
    poly = session.execute(text(
        "SELECT BlockchainID, BlockchainName FROM blockchains WHERE ChainCode = 'MATIC'"
    )).fetchone()
    polygon_id = poly[0]
    print(f"\n=== Polygon Blockchain ID: {polygon_id} ({poly[1]}) ===")
    
    # 3. Get max CurrencyID
    max_id = session.execute(
        text("SELECT MAX(CAST(CurrencyID AS UNSIGNED)) FROM currencies")
    ).fetchone()[0]
    new_id = max_id + 1
    print(f"Next available CurrencyID: {new_id}")
    
    # 4. Check if POL on Polygon already exists
    existing = session.execute(text(
        "SELECT CurrencyID FROM currencies WHERE Symbol = 'POL' AND BlockchainID = :bid"
    ), {'bid': polygon_id}).fetchone()
    
    if existing:
        print(f"\n⚠️  POL on Polygon already exists with CurrencyID={existing[0]}")
        print("No insert needed.")
    else:
        # 5. Insert the new record
        print(f"\n=== Inserting POL on Polygon with CurrencyID={new_id} ===")
        session.execute(text("""
            INSERT INTO currencies (CurrencyID, CurrencyName, Symbol, Icon, BlockchainID,
                                    DecimalPlaces, IsToken, SmartContractAddress)
            VALUES (:cid, :cname, :sym, :icon, :bid, :dec, :token, :contract)
        """), {
            'cid': str(new_id),
            'cname': 'POL (POLYGON)',
            'sym': 'POL',
            'icon': 'https://s2.coinmarketcap.com/static/img/coins/64x64/28321.png',
            'bid': polygon_id,
            'dec': 18,
            'token': 1,
            'contract': '0x0000000000000000000000000000000000001010',  # POL native on Polygon
        })
        session.commit()
        print("✅ POL (Polygon) record inserted successfully!")
        
        # Verify
        verify = session.execute(text(
            "SELECT CurrencyID, CurrencyName, Symbol, BlockchainID FROM currencies WHERE CurrencyID = :cid"
        ), {'cid': str(new_id)}).fetchone()
        print(f"Verified: ID={verify[0]}, Name={verify[1]}, Symbol={verify[2]}, BlockchainID={verify[3]}")

finally:
    session.close()
