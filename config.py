import os

# DATABASE_URL = "postgresql://username:password@localhost/database_name"
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///mydatabase.db")
BOT_TOKEN = os.environ["CHECK_SID_BOT_TOKEN"]

MAX_RECORDS_PER_USER = 5

REPLY_WITH_PHOTO_ID_USER_IDS = {
    int(x) for x in os.environ.get("REPLY_WITH_PHOTO_ID_USER_IDS", "").split(";") if x
}

MOSCOW_SID_DATABASE_URL = os.environ["MOSCOW_SID_DATABASE_URL"]
