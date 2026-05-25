from ..database import init_storage
from ..repository import init_db


def bootstrap_runtime():
    init_storage()
    init_db()
