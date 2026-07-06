"""Clean up test data from price_alerts table."""
from database import SessionLocal, PriceAlert
session = SessionLocal()
for uid_pattern in ['test', 'diag', 'deploy']:
    rows = session.query(PriceAlert).filter(PriceAlert.user_id.like(f'%{uid_pattern}%')).all()
    for r in rows:
        session.delete(r)
session.commit()
remaining = session.query(PriceAlert).count()
session.close()
print(f'Cleaned up. Remaining alerts: {remaining}')
