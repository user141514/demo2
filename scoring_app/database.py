import os
import sqlite3
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = APP_ROOT / "data"
DEFAULT_UPLOAD_DIR = APP_ROOT / "uploads"


def get_data_dir():
    return Path(os.getenv("SCORING_APP_DATA_DIR", str(DEFAULT_DATA_DIR)))


def get_upload_dir():
    return Path(os.getenv("SCORING_APP_UPLOAD_DIR", str(DEFAULT_UPLOAD_DIR)))


def get_db_path():
    default_path = get_data_dir() / "scores.db"
    return Path(os.getenv("SCORING_APP_DB_PATH", str(default_path)))


def init_storage():
    get_data_dir().mkdir(parents=True, exist_ok=True)
    get_upload_dir().mkdir(parents=True, exist_ok=True)


def get_connection():
    connection = sqlite3.connect(str(get_db_path()))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
