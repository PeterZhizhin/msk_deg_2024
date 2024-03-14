from sqlalchemy import create_engine, Column, Integer, String, BigInteger, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import config

Base = declarative_base()


class VoterRecord(Base):
    __tablename__ = "voter_records"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=False)
    transaction_id = Column(String, nullable=False)
    voter_key = Column(String, nullable=True)
    region = Column(String, nullable=False)


class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    do_not_send = Column(Boolean)


engine = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)
