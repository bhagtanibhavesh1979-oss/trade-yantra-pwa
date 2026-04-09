from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String, primary_key=True, index=True) # session_id (UUID)
    client_id = Column(String, index=True)
    jwt_token = Column(String)
    feed_token = Column(String)
    api_key = Column(String)
    is_paused = Column(Boolean, default=False)
    auto_paper_trade = Column(Boolean, default=False) # Enable virtual trades on alerts
    virtual_balance = Column(Float, default=100000.0) # Virtual wallet balance
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)

    # Relationships
    watchlist = relationship("WatchlistItem", back_populates="session", cascade="all, delete-orphan")
    alerts = relationship("AlertItem", back_populates="session", cascade="all, delete-orphan")
    logs = relationship("LogItem", back_populates="session", cascade="all, delete-orphan")
    paper_trades = relationship("VirtualTrade", back_populates="session", cascade="all, delete-orphan")

class VirtualTrade(Base):
    __tablename__ = "virtual_trades"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("user_sessions.id"))
    symbol = Column(String)
    token = Column(String)
    side = Column(String) # BUY, SELL
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Integer, default=1)
    status = Column(String, default="OPEN") # OPEN, CLOSED
    pnl = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    session = relationship("UserSession", back_populates="paper_trades")

class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("user_sessions.id"))
    symbol = Column(String)
    token = Column(String)
    exch_seg = Column(String)
    pdc = Column(Float, nullable=True)
    pdh = Column(Float, nullable=True)
    pdl = Column(Float, nullable=True)

    session = relationship("UserSession", back_populates="watchlist")

class AlertItem(Base):
    __tablename__ = "alert_items"

    id = Column(Integer, primary_key=True, index=True) # auto-increment PK
    alert_id = Column(String, index=True) # Original UUID for frontend tracking
    session_id = Column(String, ForeignKey("user_sessions.id"))
    symbol = Column(String)
    token = Column(String)
    condition = Column(String) # ABOVE, BELOW
    price = Column(Float)
    active = Column(Boolean, default=True)
    type = Column(String, default="MANUAL") # Added to track AUTO vs MANUAL
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("UserSession", back_populates="alerts")

class LogItem(Base):
    __tablename__ = "log_items"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("user_sessions.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    symbol = Column(String)
    message = Column(String)
    type = Column(String) # info, alert_triggered
    current_price = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)

    session = relationship("UserSession", back_populates="logs")

class ScripMaster(Base):
    __tablename__ = "scrip_master"

    token = Column(String, primary_key=True, index=True)
    symbol = Column(String, index=True)
    name = Column(String)
    expiry = Column(String, nullable=True)
    strike = Column(String, nullable=True)
    lotsize = Column(String, nullable=True)
    instrumenttype = Column(String, nullable=True)
    exch_seg = Column(String)
    tick_size = Column(String, nullable=True)
