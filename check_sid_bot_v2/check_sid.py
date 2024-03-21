import dataclasses
import datetime
import enum
import functools
from typing import Any, Self
import logging
import uuid

import pytz
from sqlalchemy import create_engine, Column, Integer, String
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


class CandidateIdToName(Base):
    __tablename__ = "candidate_id_to_name"
    candidate_id = Column(Integer, primary_key=True)
    candidate_name = Column(String)

    def __repr__(self):
        return f"<CandidateIdToName(id={self.id}, name={self.name})>"


if not config.MOSCOW_SID_DATABASE_URL:
    logger.error(
        "MOSCOW_SID_DATABASE_URL environment variable not set. Disabling database."
    )
    _engine = None
    _SessionLocal = None
else:
    _engine = create_engine(config.MOSCOW_SID_DATABASE_URL)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@functools.lru_cache(maxsize=128)
def _candidate_id_to_name_mapping() -> dict[int, str] | None:
    if _SessionLocal is None:
        return None

    with _SessionLocal() as session:
        logger.info("Querying candidate_id_to_name")
        result = session.query(CandidateIdToName).all()
        result_dict = {}
        for x in result:
            candidate_id = x.candidate_id
            candidate_name = x.candidate_name

            if candidate_id is None:
                raise ValueError(f"Invalid candidate_id: {candidate_id}")
            if candidate_name is None:
                raise ValueError(f"Invalid candidate_name: {candidate_name}")

            candidate_id = int(candidate_id)
            candidate_name = str(candidate_name)

            result_dict[candidate_id] = candidate_name
        return result_dict


def candidate_id_to_name(candidate_id: int) -> str | None:
    mapping = _candidate_id_to_name_mapping()
    if mapping is None:
        raise ValueError("Database not initialized")
    return mapping.get(candidate_id)


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
    decrypted_value: list[int]
    timestamp: datetime.datetime
    raw_data: Any

    @classmethod
    def from_json(cls, x: Any) -> Self:
        if not isinstance(x, dict):
            raise ValueError(f"Invalid StorageDecodeBallot: {x}")

        timestamp_val = x.get("Timestamp")
        decrypted_value = x.get("DecryptedValue")

        if not isinstance(timestamp_val, int):
            raise ValueError(f"Invalid timestamp: {timestamp_val}. {x=}")
        if not isinstance(decrypted_value, list) or any(
            not isinstance(x, int) for x in decrypted_value
        ):
            raise ValueError(f"Invalid data: {decrypted_value}. {x=}")

        timestamp = datetime.datetime.fromtimestamp(
            timestamp_val, datetime.timezone.utc
        )

        return cls(
            decrypted_value=decrypted_value,
            timestamp=timestamp,
            raw_data=x,
        )

    def to_json(self) -> Any:
        return self.raw_data

    def human_readable(self) -> str:
        desired_timezone = pytz.timezone("Europe/Moscow")
        local_time = self.timestamp.astimezone(desired_timezone)
        time_str = local_time.strftime("%Y-%m-%d %H:%M:%S")

        candidate_names = [candidate_id_to_name(x) for x in self.decrypted_value]
        candidate_names_joined = ", ".join(str(x) for x in candidate_names)

        return f"""
За кого расшифровалось: {candidate_names_joined}
Время расшифровки (московское время): {time_str}
""".strip()


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
        return_base = f"""
Адрес транзакции: {self.sid}
Через что голосовали: {self.storage_ballot.source.human_readable()}
Время приёма бюллетеня (московское время): {time_str}
""".strip()

        data_field = f"Поле data: {self.storage_ballot.data}"

        voting_not_finished = f"""
{data_field}

Пока тут есть только информация о приёме бюллетеня. Информация о том, за кого учёлся голос будет доступна после подведения итогов.
""".strip()

        decrypted_human_readable = None
        if self.storage_decode_ballot is not None:
            decrypted_human_readable = (
                "\n" + self.storage_decode_ballot.human_readable()
            )

        ending_message = decrypted_human_readable or voting_not_finished

        return f"""
{return_base}
{ending_message}
"""

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


def message_to_sid(message: str) -> str:
    original_message = message
    message = message.strip().lower()
    allowed_symbols = set("0123456789abcdef-")
    sid_str = "".join(x for x in message if x in allowed_symbols)
    logging.info(f"Converting message {original_message} to sid {sid_str}")
    return sid_str


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
