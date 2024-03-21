from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    BigInteger,
    Boolean,
    DateTime,
)
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


class CheckingSids(Base):
    __tablename__ = "checking_sids"
    # DO NOT STORE TELEGRAM USER ID HERE
    # IF WE DO, WE'LL BE ABLE TO LINK TELEGRAM USER ID TO VOTER RECORDS
    row_id = Column(Integer, primary_key=True, autoincrement=True)
    check_timestamp = Column(DateTime(timezone=True), nullable=False)
    sid = Column(String, nullable=False)
    found_sid = Column(Boolean, nullable=False)
    error_info = Column(String, nullable=True)
    tx_info = Column(String, nullable=True)

    def __repr__(self):
        return (
            f"<CheckingSids(\n"
            f"  row_id={self.row_id},\n"
            f"  check_timestamp={self.check_timestamp},\n"
            f"  sid='{self.sid}',\n"
            f"  found_sid={self.found_sid},\n"
            f"  error_info='{self.error_info}',\n"
            f"  tx_info='{self.tx_info}'\n"
            f")>"
        )


class User(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    do_not_send = Column(Boolean)


engine = create_engine(config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)
