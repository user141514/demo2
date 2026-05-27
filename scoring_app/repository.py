import json

from .database import get_connection


def init_db():
    connection = get_connection()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id
            ON user_sessions(user_id);

            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                token_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id
            ON password_reset_tokens(user_id);

            CREATE TABLE IF NOT EXISTS scores (
                score_id TEXT PRIMARY KEY,
                user_id TEXT,
                name TEXT NOT NULL,
                org TEXT NOT NULL,
                report_type TEXT NOT NULL,
                course_session TEXT,
                score_date TEXT NOT NULL,
                note TEXT,
                pdf_filename TEXT,
                upload_path TEXT,
                document_preview TEXT,
                transcript_present INTEGER NOT NULL,
                total_score REAL NOT NULL,
                total_level TEXT NOT NULL,
                doc_average REAL,
                audio_average REAL,
                lowest_dimension_name TEXT,
                lowest_dimension_score REAL,
                overall_comment TEXT NOT NULL,
                strengths_json TEXT NOT NULL,
                improvements_json TEXT NOT NULL,
                disclaimer TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS score_dimensions (
                score_id TEXT NOT NULL,
                dimension_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                group_name TEXT NOT NULL,
                group_weight REAL NOT NULL,
                actual_weight REAL NOT NULL,
                material_source TEXT NOT NULL,
                score REAL,
                level_label TEXT,
                evidence TEXT NOT NULL,
                comment TEXT,
                PRIMARY KEY (score_id, dimension_id),
                FOREIGN KEY (score_id) REFERENCES scores(score_id)
            );
            """
        )
        _ensure_column(
            connection,
            "scores",
            "user_id",
            "ALTER TABLE scores ADD COLUMN user_id TEXT REFERENCES users(user_id)",
        )
        _ensure_column(
            connection,
            "scores",
            "course_session",
            "ALTER TABLE scores ADD COLUMN course_session TEXT",
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scores_user_id
            ON scores(user_id)
            """
        )
        connection.commit()
    finally:
        connection.close()


def _ensure_column(connection, table_name, column_name, alter_sql):
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info({})".format(table_name))
    }
    if column_name not in columns:
        connection.execute(alter_sql)


def create_user(user_id, email, display_name, password_hash, created_at):
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO users (user_id, email, display_name, password_hash, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, email, display_name, password_hash, created_at, created_at),
        )
        connection.commit()
    finally:
        connection.close()


def count_users():
    connection = get_connection()
    try:
        row = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()
        return row["total"] if row is not None else 0
    finally:
        connection.close()


def claim_orphan_scores(user_id):
    connection = get_connection()
    try:
        connection.execute(
            """
            UPDATE scores
            SET user_id = ?
            WHERE user_id IS NULL OR TRIM(user_id) = ''
            """,
            (user_id,),
        )
        connection.commit()
    finally:
        connection.close()


def get_user_by_email(email):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT user_id, email, display_name, password_hash, created_at, updated_at
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()
        return _serialize_user(row)
    finally:
        connection.close()


def get_user_by_id(user_id):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT user_id, email, display_name, password_hash, created_at, updated_at
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        return _serialize_user(row)
    finally:
        connection.close()


def update_user_password(user_id, password_hash, updated_at):
    connection = get_connection()
    try:
        connection.execute(
            """
            UPDATE users
            SET password_hash = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (password_hash, updated_at, user_id),
        )
        connection.commit()
    finally:
        connection.close()


def create_user_session(session_id, user_id, token_hash, created_at, expires_at):
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO user_sessions (session_id, user_id, token_hash, created_at, expires_at, revoked_at)
            VALUES (?, ?, ?, ?, ?, NULL)
            """,
            (session_id, user_id, token_hash, created_at, expires_at),
        )
        connection.commit()
    finally:
        connection.close()


def get_active_session(token_hash, now_value):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT s.session_id, s.user_id, s.token_hash, s.created_at, s.expires_at, s.revoked_at,
                   u.email, u.display_name, u.password_hash, u.created_at AS user_created_at,
                   u.updated_at AS user_updated_at
            FROM user_sessions s
            JOIN users u ON u.user_id = s.user_id
            WHERE s.token_hash = ?
              AND s.revoked_at IS NULL
              AND s.expires_at > ?
            """,
            (token_hash, now_value),
        ).fetchone()
        if row is None:
            return None
        return {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "token_hash": row["token_hash"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "user": {
                "user_id": row["user_id"],
                "email": row["email"],
                "display_name": row["display_name"],
                "password_hash": row["password_hash"],
                "created_at": row["user_created_at"],
                "updated_at": row["user_updated_at"],
            },
        }
    finally:
        connection.close()


def revoke_session(token_hash, revoked_at):
    connection = get_connection()
    try:
        connection.execute(
            """
            UPDATE user_sessions
            SET revoked_at = ?
            WHERE token_hash = ? AND revoked_at IS NULL
            """,
            (revoked_at, token_hash),
        )
        connection.commit()
    finally:
        connection.close()


def revoke_user_sessions(user_id, revoked_at):
    connection = get_connection()
    try:
        connection.execute(
            """
            UPDATE user_sessions
            SET revoked_at = ?
            WHERE user_id = ? AND revoked_at IS NULL
            """,
            (revoked_at, user_id),
        )
        connection.commit()
    finally:
        connection.close()


def create_password_reset_token(token_id, user_id, token_hash, created_at, expires_at):
    connection = get_connection()
    try:
        connection.execute(
            """
            UPDATE password_reset_tokens
            SET used_at = ?
            WHERE user_id = ? AND used_at IS NULL
            """,
            (created_at, user_id),
        )
        connection.execute(
            """
            INSERT INTO password_reset_tokens (token_id, user_id, token_hash, created_at, expires_at, used_at)
            VALUES (?, ?, ?, ?, ?, NULL)
            """,
            (token_id, user_id, token_hash, created_at, expires_at),
        )
        connection.commit()
    finally:
        connection.close()


def get_active_password_reset_token(token_hash, now_value):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT token_id, user_id, token_hash, created_at, expires_at, used_at
            FROM password_reset_tokens
            WHERE token_hash = ?
              AND used_at IS NULL
              AND expires_at > ?
            """,
            (token_hash, now_value),
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        connection.close()


def consume_password_reset_token(token_id, used_at):
    connection = get_connection()
    try:
        connection.execute(
            """
            UPDATE password_reset_tokens
            SET used_at = ?
            WHERE token_id = ? AND used_at IS NULL
            """,
            (used_at, token_id),
        )
        connection.commit()
    finally:
        connection.close()


def store_score(result):
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO scores (
                score_id, user_id, name, org, report_type, course_session, score_date, note, pdf_filename,
                upload_path, document_preview, transcript_present, total_score,
                total_level, doc_average, audio_average, lowest_dimension_name,
                lowest_dimension_score, overall_comment, strengths_json,
                improvements_json, disclaimer, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["score_id"],
                result["user_id"],
                result["name"],
                result["org"],
                result["report_type"],
                result.get("course_session", ""),
                result["date"],
                result["note"],
                result["pdf_filename"],
                result["upload_path"],
                result["document_preview"],
                1 if result["transcript_present"] else 0,
                result["total_score"],
                result["total_level"],
                result["doc_average"],
                result["audio_average"],
                result["lowest_dimension"]["name"],
                result["lowest_dimension"]["score"],
                result["overall_comment"],
                json.dumps(result["strengths"], ensure_ascii=False),
                json.dumps(result["improvements"], ensure_ascii=False),
                result["disclaimer"],
                result["created_at"],
            ),
        )
        for dimension in result["dimensions"]:
            connection.execute(
                """
                INSERT INTO score_dimensions (
                    score_id, dimension_id, name, group_name, group_weight,
                    actual_weight, material_source, score, level_label, evidence, comment
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result["score_id"],
                    dimension["id"],
                    dimension["name"],
                    dimension["group_name"],
                    dimension["group_weight"],
                    dimension["actual_weight"],
                    dimension["material_source"],
                    dimension["score"],
                    dimension["level_label"],
                    dimension["evidence"],
                    dimension["comment"],
                ),
            )
        connection.commit()
    finally:
        connection.close()


def list_scores(user_id):
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT score_id, name, org, report_type, course_session, score_date, total_score,
                   total_level, created_at
            FROM scores
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()
        return {
            "items": [
                {
                    "score_id": row["score_id"],
                    "name": row["name"],
                    "org": row["org"],
                    "report_type": row["report_type"],
                    "course_session": row["course_session"] or "",
                    "date": row["score_date"],
                    "total_score": row["total_score"],
                    "total_level": row["total_level"],
                    "manual_score": None,
                    "manual_score_status": "pending",
                    "created_at": row["created_at"],
                }
                for row in rows
            ],
            "manual_gap_summary": {
                "average_gap": None,
                "compared_count": 0,
                "status": "pending",
            },
        }
    finally:
        connection.close()


def get_score_detail(score_id, user_id):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT * FROM scores
            WHERE score_id = ? AND user_id = ?
            """,
            (score_id, user_id),
        ).fetchone()
        if row is None:
            return None

        dimensions = connection.execute(
            """
            SELECT dimension_id, name, group_name, group_weight, actual_weight,
                   material_source, score, level_label, evidence, comment
            FROM score_dimensions
            WHERE score_id = ?
            ORDER BY dimension_id ASC
            """,
            (score_id,),
        ).fetchall()

        return {
            "score_id": row["score_id"],
            "name": row["name"],
            "org": row["org"],
            "report_type": row["report_type"],
            "course_session": row["course_session"] or "",
            "date": row["score_date"],
            "note": row["note"] or "",
            "pdf_filename": row["pdf_filename"] or "",
            "document_preview": row["document_preview"] or "",
            "transcript_present": bool(row["transcript_present"]),
            "created_at": row["created_at"],
            "total_score": row["total_score"],
            "total_level": row["total_level"],
            "doc_average": row["doc_average"],
            "audio_average": row["audio_average"],
            "lowest_dimension": {
                "name": row["lowest_dimension_name"],
                "score": row["lowest_dimension_score"],
            },
            "overall_comment": row["overall_comment"],
            "strengths": json.loads(row["strengths_json"]),
            "improvements": json.loads(row["improvements_json"]),
            "disclaimer": row["disclaimer"],
            "markdown_export_url": "/api/scores/{}/export?format=md".format(row["score_id"]),
            "pdf_export_url": "/api/scores/{}/export?format=pdf".format(row["score_id"]),
            "dimensions": [
                {
                    "id": dimension["dimension_id"],
                    "name": dimension["name"],
                    "group_name": dimension["group_name"],
                    "group_weight": dimension["group_weight"],
                    "actual_weight": dimension["actual_weight"],
                    "material_source": dimension["material_source"],
                    "score": dimension["score"],
                    "level_label": dimension["level_label"],
                    "evidence": dimension["evidence"],
                    "comment": dimension["comment"] or "",
                }
                for dimension in dimensions
            ],
        }
    finally:
        connection.close()


def _serialize_user(row):
    if row is None:
        return None
    return {
        "user_id": row["user_id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "password_hash": row["password_hash"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
