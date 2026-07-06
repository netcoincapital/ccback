"""Test database connection with URL-encoded password."""
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

pw = os.getenv("DB_PASSWORD", "")
user = os.getenv("DB_USER", "coincee")
host = os.getenv("DB_HOST", "127.0.0.1")
db = os.getenv("DB_NAME", "coincee")
driver = os.getenv("DB_DRIVER", "pymysql")

encoded_pw = quote_plus(pw)
url = f"mysql+{driver}://{user}:{encoded_pw}@{host}/{db}"

print(f"URL prefix: mysql+{driver}://{user}:****@{host}/{db}")
print(f"Password length: {len(pw)}")
print(f"Encoded length: {len(encoded_pw)}")

from sqlalchemy import create_engine, text
try:
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        r = conn.execute(text("SELECT 1")).first()
        print(f"DB CONNECTION: SUCCESS - result={r[0]}")
except Exception as e:
    print(f"DB CONNECTION: FAILED - {type(e).__name__}: {str(e)[:200]}")
