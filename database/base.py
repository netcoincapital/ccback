# database/base.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get database configuration from environment variables
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'coinceeper')

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
