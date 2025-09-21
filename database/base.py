# database/base.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

# Load environment variables from .env file
# Try to find .env file in current directory or parent directories
import pathlib
current_dir = pathlib.Path(__file__).parent.parent  # Go to project root
env_path = current_dir / '.env'

# Debug: Check if .env file exists
if env_path.exists():
    print(f"Loading .env from: {env_path}")
    load_dotenv(dotenv_path=env_path)
else:
    print(f".env file not found at: {env_path}")
    # Try current directory
    env_path_current = pathlib.Path('.env')
    if env_path_current.exists():
        print(f"Loading .env from current directory: {env_path_current.absolute()}")
        load_dotenv(dotenv_path=env_path_current)
    else:
        print("No .env file found in current directory either")
        load_dotenv()  # Try default behavior

# Get database configuration from environment variables
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'coinceeper')

# Debug: Print loaded values (mask password)
print(f"DB_USER: {DB_USER}")
print(f"DB_PASSWORD: {'*' * len(DB_PASSWORD) if DB_PASSWORD else None}")
print(f"DB_HOST: {DB_HOST}")
print(f"DB_NAME: {DB_NAME}")

# Validate required environment variables
if not DB_USER or not DB_PASSWORD:
    raise ValueError("""
    Database configuration is missing. Please set the following environment variables:
    - DB_USER: Database username
    - DB_PASSWORD: Database password
    
    You can set these in your .env file:
    DB_USER=your_username
    DB_PASSWORD=your_password
    DB_HOST=localhost
    DB_NAME=coinceeper
    """)

# Construct database URL from environment variables
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

# Create engine with connection pool settings
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()
