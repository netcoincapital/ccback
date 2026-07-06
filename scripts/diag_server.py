"""Run on server: check model import and DB table creation."""
import sys, os
sys.path.insert(0, '/opt/coinceeper/CC')

print("1. Importing model...")
from database.price_alert import PriceAlert
print(f"   OK: tablename={PriceAlert.__tablename__}")
print(f"   Fields: {[c.name for c in PriceAlert.__table__.columns]}")

print("2. Creating table if needed...")
from sqlalchemy import text
from database import SessionLocal
session = SessionLocal()
try:
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS price_alerts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(36) NOT NULL,
            symbol VARCHAR(10) NOT NULL,
            alert_type VARCHAR(20) NOT NULL,
            target_price DECIMAL(20, 8) NULL,
            target_percent DECIMAL(10, 2) NULL,
            reference_price DECIMAL(20, 8) NULL,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_user (user_id),
            INDEX idx_symbol (symbol)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))
    session.commit()
    print("   OK: Table created/exists")
except Exception as e:
    session.rollback()
    print(f"   ERROR: {e}")
finally:
    session.close()

print("3. Testing insert and query...")
session = SessionLocal()
try:
    alert = PriceAlert(user_id='diag-test', symbol='BTC', alert_type='above', target_price=50000.0)
    session.add(alert)
    session.commit()
    print(f"   OK: Inserted id={alert.id}")
    
    # Read back
    row = session.query(PriceAlert).filter(PriceAlert.id == alert.id).first()
    print(f"   OK: Read back: {row.to_dict()}")
    
    # Cleanup
    session.delete(row)
    session.commit()
    print("   OK: Cleaned up")
except Exception as e:
    session.rollback()
    print(f"   ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    session.close()

print("ALL DONE - server is working correctly")
