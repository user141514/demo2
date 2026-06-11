from ..database import init_storage
from ..leadership_repository import init_leadership_tables
from ..repository import init_db


def bootstrap_runtime():
    init_storage()
    init_db()
    init_leadership_tables()
