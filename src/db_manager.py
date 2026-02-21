from sqlalchemy import create_engine, Column, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TradeLog(Base):
    __tablename__ = 'trades'
    id = Column(String, primary_key=True) # Order ID
    status = Column(String) # OPEN, CLOSED
    entry_price = Column(Float)
    tp_price = Column(Float)
    sl_price = Column(Float)
    timestamp = Column(DateTime)