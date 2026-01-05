import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# The connection string will be provided by the user or set in env
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback to local sqlite for development if no Postgres URL provided
    DATABASE_URL = "sqlite:///./trade_yantra.db"
    
# Neon/Postgres requires extra handling for SSL if using certain drivers
# but sqlalchemy generally handles it via the connection string query params
# e.g. postgres://...?sslmode=require

engine = create_engine(
    DATABASE_URL, 
    # pool_pre_ping=True is recommended for cloud databases to handle idle timeouts
    pool_pre_ping=True,
    # SQLite doesn't support multiple threads by default, but we'll use Postgres mostly
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
