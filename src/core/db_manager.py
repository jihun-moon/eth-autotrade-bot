import os
from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

# 1. 매매 이력 테이블 (성적 분석용)
class TradeHistory(Base):
    __tablename__ = 'trade_history'
    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_time = Column(DateTime)
    exit_time = Column(DateTime)
    pos_type = Column(String)  # LONG / SHORT
    entry_price = Column(Float)
    exit_price = Column(Float)
    pnl_usdt = Column(Float)
    roe_pct = Column(Float)
    exit_reason = Column(String)  # TP / SL / LIQ

# 2. 현재 포지션 상태 테이블 (서버 재시작 복구용)
class ActivePosition(Base):
    __tablename__ = 'active_position'
    id = Column(Integer, primary_key=True)
    pos_type = Column(String)
    entry_time = Column(DateTime)
    entry_price = Column(Float)
    amount = Column(Float)
    margin = Column(Float)
    entry_fee = Column(Float)

# DB 연결 세팅
DB_URL = "sqlite:///data/reports/trading_bot.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    os.makedirs("data/reports", exist_ok=True)
    Base.metadata.create_all(bind=engine)