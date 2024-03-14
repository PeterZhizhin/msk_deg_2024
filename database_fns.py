import database

from telegram import Update


def ensure_user_in_db(update: Update):
    user_id = update.effective_user.id
    with database.SessionLocal() as session:
        with session.begin():
            user = database.User(user_id=user_id)
            session.merge(user)
            return user
