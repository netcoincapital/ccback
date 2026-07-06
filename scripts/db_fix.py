"""Test database connection and diagnose."""
import os
import sys
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

pw = os.getenv("DB_PASSWORD", "")
print(f"PW present: {bool(pw)}, len: {len(pw)}")

user = os.getenv("DB_USER", "coincee")
host = os.getenv("DB_HOST", "127.0.0.1")
dbname = os.getenv("DB_NAME", "coincee")
driver = os.getenv("DB_DRIVER", "pymysql")

encoded_pw = quote_plus(pw)
# Build URL without using @ symbol inline to avoid PowerShell issues
url_parts = ["mysql+", driver, "://", user, ":", encoded_pw, host, "/", dbname]
url = "".join(url_parts)

from sqlalchemy import create_engine, text

try:
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        r = conn.execute(text("SELECT 1")).first()
        print(f"DB OK: {r[0]}")
except Exception as e:
    print(f"DB FAIL: {type(e).__name__}")
    err_str = str(e)
    if "Access denied" in err_str:
        print("-> Access denied - password mismatch")
        # Try with pymysql default fallback
        try:
            url2 = "mysql+pymysql://coincee:09387270277Mn%21%21%3F%3F@127.0.0.1/coincee"
            engine2 = create_engine(url2, pool_pre_ping=True)
            with engine2.connect() as conn2:
                r2 = conn2.execute(text("SELECT 1")).first()
                print(f"DB OK with hardcoded: {r2[0]}")
        except Exception as e2:
            print(f"DB FAIL with hardcoded too: {type(e2).__name__}")
            # Try without password
            try:
                url3 = "mysql+pymysql://coincee@127.0.0.1/coincee"
                engine3 = create_engine(url3, pool_pre_ping=True)
                with engine3.connect() as conn3:
                    r3 = conn3.execute(text("SELECT 1")).first()
                    print(f"DB OK without password: {r3[0]}")
            except Exception as e3:
                print(f"DB FAIL without password: {type(e3).__name__}")
    else:
        print(f"Error: {err_str[:300]}")
