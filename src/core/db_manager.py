from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

Base = declarative_base()

class ActivePosition(Base):
    __tablename__ = 'active_positions'
    id = Column(Integer, primary_key=True)
    pos_type = Column(String)
    entry_price = Column(Float)
    amount = Column(Float)
    margin = Column(Float)
    tp_pct = Column(Float)
    sl_pct = Column(Float)
    entry_time = Column(DateTime)

# DB 초기화
engine = create_engine('sqlite:///data/trade_bot.db')
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)