import json
import datetime
import logging

from telegram import Update

import config
import check_sid
import database

logger = logging.getLogger(__name__)


def ensure_user_in_db(update: Update):
    user_id = update.effective_user.id
    with database.SessionLocal() as session:
        with session.begin():
            user = database.User(user_id=user_id)
            session.merge(user)
            return user


def persist_sid_data(
    *,
    sid: str,
    error_info: str | None,
    sid_data: check_sid.SidQueryResult | None,
) -> None:
    if sid == config.HARDCODED_MOSCOW_VALID_SID:
        logger.info(f"Skipping persisting test sid: {sid}")
        return

    found_sid = sid_data is not None
    tx_info = None if sid_data is None else sid_data.to_json()
    check_timestamp = datetime.datetime.now(datetime.timezone.utc)

    if tx_info is not None:
        tx_info = json.dumps(tx_info)

    kwargs = {}
    if error_info is not None:
        kwargs["error_info"] = error_info

    row = database.CheckingSids(
        check_timestamp=check_timestamp,
        sid=sid,
        found_sid=found_sid,
        tx_info=tx_info,
        **kwargs,
    )
    with database.SessionLocal() as session:
        with session.begin():
            session.add(row)
        logger.info(f"Successfully persisted check sid row:\n{row}")
