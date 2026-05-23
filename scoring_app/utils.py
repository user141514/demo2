import re
from datetime import datetime
from uuid import uuid4

from werkzeug.utils import secure_filename

from .database import get_upload_dir


def now_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def slugify_filename(filename):
    secured = secure_filename(filename)
    if secured:
        return secured
    return re.sub(r"[^A-Za-z0-9._-]+", "_", filename) or "upload.bin"


def save_upload(filename, content, folder_name="pdfs"):
    target_dir = get_upload_dir() / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_name = "{}_{}".format(uuid4().hex[:8], slugify_filename(filename))
    target_path = target_dir / saved_name
    target_path.write_bytes(content)
    return target_path
