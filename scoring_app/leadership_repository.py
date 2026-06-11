import json
from uuid import uuid4

from .database import get_connection


def init_leadership_tables():
    connection = get_connection()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS leadership_models (
                model_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                context_json TEXT NOT NULL,
                dimensions_json TEXT NOT NULL DEFAULT '[]',
                descriptions_json TEXT NOT NULL DEFAULT '[]',
                anchors_json TEXT NOT NULL DEFAULT '[]',
                dimensions_confirmed INTEGER NOT NULL DEFAULT 0,
                descriptions_confirmed INTEGER NOT NULL DEFAULT 0,
                anchors_confirmed INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                current_step TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_leadership_models_user_id
            ON leadership_models(user_id);

            CREATE TABLE IF NOT EXISTS leadership_model_artifacts (
                artifact_id TEXT PRIMARY KEY,
                model_id TEXT NOT NULL,
                artifact_kind TEXT NOT NULL,
                filename TEXT NOT NULL,
                mimetype TEXT NOT NULL,
                content_bytes BLOB NOT NULL,
                byte_size INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (model_id) REFERENCES leadership_models(model_id) ON DELETE CASCADE
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_leadership_artifact_kind
            ON leadership_model_artifacts(model_id, artifact_kind);
            """
        )
        connection.commit()
    finally:
        connection.close()


def create_leadership_model(record, artifacts=None):
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO leadership_models (
                model_id, user_id, title, context_json, dimensions_json,
                descriptions_json, anchors_json, dimensions_confirmed,
                descriptions_confirmed, anchors_confirmed, status,
                current_step, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["model_id"],
                record["user_id"],
                record["title"],
                _dumps(record.get("context") or {}),
                _dumps(record.get("dimensions") or []),
                _dumps(record.get("descriptions") or []),
                _dumps(record.get("anchors") or []),
                1 if record.get("dimensions_confirmed") else 0,
                1 if record.get("descriptions_confirmed") else 0,
                1 if record.get("anchors_confirmed") else 0,
                record["status"],
                record["current_step"],
                record["created_at"],
                record["updated_at"],
            ),
        )
        for artifact in artifacts or []:
            _upsert_leadership_artifact(connection, record["model_id"], artifact)
        connection.commit()
    finally:
        connection.close()


def update_leadership_model(model_id, user_id, updates):
    allowed = {
        "title",
        "context",
        "dimensions",
        "descriptions",
        "anchors",
        "dimensions_confirmed",
        "descriptions_confirmed",
        "anchors_confirmed",
        "status",
        "current_step",
        "updated_at",
    }
    parts = []
    params = []
    for key, value in updates.items():
        if key not in allowed:
            continue
        column = _column_for_key(key)
        if key in {"context", "dimensions", "descriptions", "anchors"}:
            value = _dumps(value)
        elif key.endswith("_confirmed"):
            value = 1 if value else 0
        parts.append("{} = ?".format(column))
        params.append(value)
    if not parts:
        return None

    params.extend([model_id, user_id])
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE leadership_models SET {} WHERE model_id = ? AND user_id = ?".format(
                ", ".join(parts)
            ),
            params,
        )
        connection.commit()
    finally:
        connection.close()
    return get_leadership_model(model_id, user_id)


def get_leadership_model(model_id, user_id):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT * FROM leadership_models WHERE model_id = ? AND user_id = ?",
            (model_id, user_id),
        ).fetchone()
        return _row_to_model(row)
    finally:
        connection.close()


def list_leadership_models(user_id):
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT * FROM leadership_models
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [_row_to_model(row) for row in rows]
    finally:
        connection.close()


def store_leadership_artifact(model_id, artifact):
    connection = get_connection()
    try:
        result = _upsert_leadership_artifact(connection, model_id, artifact)
        connection.commit()
        return result
    finally:
        connection.close()


def get_leadership_artifact(model_id, artifact_kind):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT artifact_id, model_id, artifact_kind, filename, mimetype,
                   content_bytes, byte_size, created_at
            FROM leadership_model_artifacts
            WHERE model_id = ? AND artifact_kind = ?
            """,
            (model_id, artifact_kind),
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        connection.close()


def _upsert_leadership_artifact(connection, model_id, artifact):
    payload = bytes(artifact["content_bytes"])
    artifact_id = uuid4().hex
    connection.execute(
        "DELETE FROM leadership_model_artifacts WHERE model_id = ? AND artifact_kind = ?",
        (model_id, artifact["artifact_kind"]),
    )
    connection.execute(
        """
        INSERT INTO leadership_model_artifacts (
            artifact_id, model_id, artifact_kind, filename, mimetype,
            content_bytes, byte_size, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact_id,
            model_id,
            artifact["artifact_kind"],
            artifact["filename"],
            artifact["mimetype"],
            payload,
            len(payload),
            artifact["created_at"],
        ),
    )
    return {
        "artifact_id": artifact_id,
        "model_id": model_id,
        "artifact_kind": artifact["artifact_kind"],
        "filename": artifact["filename"],
        "mimetype": artifact["mimetype"],
        "byte_size": len(payload),
        "created_at": artifact["created_at"],
    }


def _row_to_model(row):
    if row is None:
        return None
    return {
        "model_id": row["model_id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "context": _loads(row["context_json"], {}),
        "dimensions": _loads(row["dimensions_json"], []),
        "descriptions": _loads(row["descriptions_json"], []),
        "anchors": _loads(row["anchors_json"], []),
        "dimensions_confirmed": bool(row["dimensions_confirmed"]),
        "descriptions_confirmed": bool(row["descriptions_confirmed"]),
        "anchors_confirmed": bool(row["anchors_confirmed"]),
        "status": row["status"],
        "current_step": row["current_step"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _column_for_key(key):
    return {
        "context": "context_json",
        "dimensions": "dimensions_json",
        "descriptions": "descriptions_json",
        "anchors": "anchors_json",
    }.get(key, key)


def _dumps(value):
    return json.dumps(value, ensure_ascii=False)


def _loads(value, fallback):
    try:
        return json.loads(value or "")
    except Exception:
        return fallback
