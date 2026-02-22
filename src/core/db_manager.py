import os
from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class TradeHistory(Base):
    __tablename__ = 'trade_history'
    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_time = Column(DateTime)
    exit_time = Column(DateTime)
    pos_type = Column(String)
    entry_price = Column(Float)
    exit_price = Column(Float)
    roe_pct = Column(Float)
    exit_reason = Column(String)

class ActivePosition(Base):
    __tablename__ = 'active_position'
    id = Column(Integer, primary_key=True)
    pos_type = Column(String)
    entry_time = Column(DateTime)
    entry_price = Column(Float)
    amount = Column(Float)
    margin = Column(Float)
    # [추가] 당시 결정된 동적 TP/SL 보존
    tp_pct = Column(Float)
    sl_pct = Column(Float)

DB_URL = "sqlite:///data/reports/trading_bot.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    os.makedirs("data/reports", exist_ok=True)
    Base.metadata.create_all(bind=engine)