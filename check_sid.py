import dataclasses
import datetime
import enum
from typing import Any, Self
import logging
import uuid

import pytz
from sqlalchemy import create_engine, Column, Integer, String, BigInteger, Boolean
from sqlalchemy.dialects.postgresql import JSONB  # Import JSONB type
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import config

Base = declarative_base()


logger = logging.getLogger(__name__)


class SidToStoreDecode(Base):
    __tablename__ = "sid_to_store_decode"
    sid = Column(
        String, primary_key=True
    )  # Assuming 'sid' is of type String and serves as a unique identifier
    storageballot = Column(JSONB)  # Use JSONB type for storageballot
    storagedecodeballot = Column(JSONB)  # Use JSONB type for storagedecodeballot

    def __repr__(self):
        return f"<SidToStoreDecode(sid={self.sid}, storageballot={self.storageballot}, storagedecodeballot={self.storagedecodeballot})>"


if not config.MOSCOW_SID_DATABASE_URL:
    logger.error(
        "MOSCOW_SID_DATABASE_URL environment variable not set. Disabling database."
    )
    _engine = None
    _SessionLocal = None
else:
    _engine = create_engine(config.MOSCOW_SID_DATABASE_URL)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


class Source(enum.Enum):
    DEG = "DEG"
    EVT = "EVT"

    def human_readable(self) -> str:
        match self:
            case Source.DEG:
                return "ДЭГ через интернет"
            case Source.EVT:
                return "ДЭГ на участке через терминал"


def _str_to_source(s: str) -> Source:
    match s:
        case "DEG":
            return Source.DEG
        case "EVT":
            return Source.EVT
        case _:
            raise ValueError(f"Invalid source: {s}")


@dataclasses.dataclass(frozen=True)
class StorageBallot:
    source: Source
    timestamp: datetime.datetime
    data: str
    raw_data: Any

    @classmethod
    def from_json(cls, x: Any) -> Self:
        if not isinstance(x, dict):
            raise ValueError(f"Invalid StorageBallot: {x}")

        source_val = x.get("Source")
        timestamp_val = x.get("Timestamp")
        data_val = x.get("Data")

        if not isinstance(source_val, str):
            raise ValueError(f"Invalid source: {source_val}. {x=}")
        if not isinstance(timestamp_val, int):
            raise ValueError(f"Invalid timestamp: {timestamp_val}. {x=}")
        if not isinstance(data_val, str):
            raise ValueError(f"Invalid data: {data_val}. {x=}")

        source = _str_to_source(source_val)
        timestamp = datetime.datetime.fromtimestamp(
            timestamp_val, datetime.timezone.utc
        )
        return cls(
            source=source,
            timestamp=timestamp,
            data=data_val,
            raw_data=x,
        )

    def to_json(self) -> Any:
        return self.raw_data


@dataclasses.dataclass(frozen=True)
class StorageDecodeBallot:
    raw_data: Any

    @classmethod
    def from_json(cls, x: Any) -> Self:
        return cls(
            raw_data=x,
        )

    def to_json(self) -> Any:
        return self.raw_data


@dataclasses.dataclass(frozen=True)
class SidQueryResult:
    sid: str
    storage_ballot: StorageBallot
    storage_decode_ballot: StorageDecodeBallot | None

    @classmethod
    def from_row(cls, x: SidToStoreDecode) -> Self:
        sid = str(x.sid)
        storage_ballot = StorageBallot.from_json(x.storageballot)

        storage_decode_ballot = None
        if x.storagedecodeballot is not None:
            storage_decode_ballot = StorageDecodeBallot.from_json(x.storagedecodeballot)
        return cls(
            sid=sid,
            storage_ballot=storage_ballot,
            storage_decode_ballot=storage_decode_ballot,
        )

    def human_readable(self) -> str:
        desired_timezone = pytz.timezone("Europe/Moscow")
        local_time = self.storage_ballot.timestamp.astimezone(desired_timezone)
        time_str = local_time.strftime("%Y-%m-%d %H:%M:%S")
        return f"""
Адрес транзакции: {self.sid}
Через что голосовали: {self.storage_ballot.source.human_readable()}
Время приёма бюллетеня (московское время): {time_str}
Поле data: {self.storage_ballot.data}

Пока тут есть только информация о приёме бюллетеня. Информация о том, за кого учёлся голос будет доступна после подведения итогов.
""".strip()

    def to_json(self) -> Any:
        return {
            "sid": self.sid,
            "storage_ballot": self.storage_ballot.to_json(),
            "storage_decode_ballot": (
                self.storage_decode_ballot.to_json()
                if self.storage_decode_ballot is not None
                else None
            ),
        }


def is_valid_sid(sid: str) -> bool:
    # Example: 00113b68-bdae-469a-888e-ec8b18d06238
    try:
        uuid.UUID(sid, version=4)
        return True
    except ValueError:
        return False


def query_sid(sid: str) -> SidQueryResult | None:
    if _SessionLocal is None:
        raise ValueError(
            "Tried to query SID from database without a database URL. "
            "Set MOSCOW_SID_DATABASE_URL environment variable."
        )

    with _SessionLocal() as session:
        result = (
            session.query(SidToStoreDecode).filter(SidToStoreDecode.sid == sid).first()
        )
        if result is None:
            return None
        return SidQueryResult.from_row(result)
