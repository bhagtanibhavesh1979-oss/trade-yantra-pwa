import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# The connection string will be provided by the user or set in env
# NEON / POSTGRES PERSISTENCE (Safe for Cloud Run)
DATABASE_URL = os.getenv("DATABASE_URL")

# Fallback to local SQLite ONLY if no env var is found (for local dev)
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./trade_yantra.db"

# Cleanup URL if needed (Neon often provides postgres:// which SQLAlchemy 1.4+ needs as postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
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
