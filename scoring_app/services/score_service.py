from dataclasses import dataclass

from ..core.errors import ApplicationError
from ..core.text_quality import looks_like_garbled_text
from ..markdown_export import build_markdown
from ..pdf_export import PdfBuildError, build_pdf_bytes
from ..pdf_extract import PdfExtractionError, extract_text_from_pdf_bytes
from ..repository import (
    delete_score,
    get_score_artifact,
    get_score_detail,
    list_scores,
    list_scores_paginated,
    store_score_artifact,
    store_score_bundle,
    update_score_meta,
)
from ..database import get_connection
from ..rules import REPORT_DEFINITIONS
from ..scoring import ScoringError, score_submission
from ..utils import now_iso


HIDDEN_REPORT_TYPE_OPTIONS = {"行动学习"}


COURSE_SESSION_OPTIONS = {
    "第一次课 · 管理认知",
    "第二次课 · 组织协同",
    "第三次课 · 问题解决",
    "第四次课",
    "第五次课",
    "第六次课",
    "中期回顾工作坊",
}


@dataclass
class ScoreSubmissionInput:
    name: str
    org: str
    report_type: str
    course_session: str
    score_date: str
    note: str
    transcript: str
    transcript_filename: str
    transcript_file_bytes: bytes
    pdf_file: object
    pdf_bytes: bytes


def create_score(form, files, user_id):
    submission = _parse_submission(form, files)
    return create_score_from_submission(submission, user_id)


def prepare_score_submission(form, files):
    return _parse_submission(form, files)


def create_score_from_submission(submission, user_id):
    try:
        document_text = extract_text_from_pdf_bytes(submission.pdf_bytes)
    except PdfExtractionError as exc:
        raise ApplicationError("pdf_extract_failed", str(exc), 422)

    try:
        result = score_submission(
            report_type=submission.report_type,
            document_text=document_text,
            transcript_text=submission.transcript,
            metadata={
                "name": submission.name,
                "org": submission.org,
                "course_session": submission.course_session,
                "date": submission.score_date,
                "note": submission.note,
                "pdf_filename": submission.pdf_file.filename,
                "upload_path": "",
                "document_preview": document_text[:800],
            },
        )
    except ScoringError as exc:
        raise ApplicationError("score_failed", str(exc), 422)

    result["user_id"] = user_id
    result["course_session"] = submission.course_session
    result["upload_path"] = "db://score_artifacts/{}/source_pdf".format(result["score_id"])
    result["markdown_export_url"] = "/api/scores/{}/export?format=md".format(
        result["score_id"]
    )
    result["pdf_export_url"] = "/api/scores/{}/export?format=pdf".format(
        result["score_id"]
    )
    artifacts = [
        {
            "artifact_kind": "source_pdf",
            "filename": submission.pdf_file.filename,
            "mimetype": "application/pdf",
            "content_bytes": submission.pdf_bytes,
            "created_at": result["created_at"],
        }
    ]
    if submission.transcript_file_bytes:
        artifacts.append(
            {
                "artifact_kind": "source_transcript",
                "filename": submission.transcript_filename or "transcript.txt",
                "mimetype": "text/plain",
                "content_bytes": submission.transcript_file_bytes,
                "created_at": result["created_at"],
            }
        )
    store_score_bundle(result, artifacts=artifacts)
    return result


def list_user_scores(user_id):
    return list_scores(user_id)


def list_user_scores_paginated(user_id, page=1, per_page=20):
    return list_scores_paginated(user_id, page=page, per_page=per_page)


def delete_user_score(score_id, user_id):
    connection = get_connection()
    try:
        deleted = delete_score(connection, score_id, user_id)
        connection.commit()
        if not deleted:
            raise ApplicationError("score_not_found", "Score record was not found.", 404)
    finally:
        connection.close()


def update_user_score(score_id, user_id, updates):
    connection = get_connection()
    try:
        row = update_score_meta(connection, score_id, user_id, updates)
        connection.commit()
        if row is None:
            raise ApplicationError("score_not_found", "Score record was not found.", 404)
        return get_score_detail(score_id, user_id)
    finally:
        connection.close()


def get_user_score(score_id, user_id):
    detail = get_score_detail(score_id, user_id)
    if detail is None:
        raise ApplicationError("score_not_found", "Score record was not found.", 404)
    return detail


def build_score_export(score_id, user_id, export_format):
    if export_format not in {"md", "pdf"}:
        raise ApplicationError(
            "invalid_export_format",
            "Only Markdown and PDF exports are supported.",
            400,
        )

    detail = get_user_score(score_id, user_id)
    base_name = "{}_{}_{}".format(detail["name"], detail["report_type"], detail["date"])
    artifact_kind = "export_{}".format(export_format)
    cached_artifact = get_score_artifact(score_id, artifact_kind)
    if cached_artifact is not None:
        return {
            "content": cached_artifact["content_bytes"],
            "filename": cached_artifact["filename"],
            "mimetype": cached_artifact["mimetype"],
        }

    if export_format == "md":
        markdown = build_markdown(detail)
        filename = "{}.md".format(base_name)
        content_bytes = markdown.encode("utf-8")
        store_score_artifact(
            score_id,
            artifact_kind,
            filename,
            "text/markdown; charset=utf-8",
            content_bytes,
            now_iso(),
        )
        return {
            "content": content_bytes,
            "filename": filename,
            "mimetype": "text/markdown; charset=utf-8",
        }

    try:
        pdf_bytes = build_pdf_bytes(detail)
    except PdfBuildError as exc:
        raise ApplicationError("pdf_export_failed", str(exc), 500)

    filename = "{}.pdf".format(base_name)
    store_score_artifact(
        score_id,
        artifact_kind,
        filename,
        "application/pdf",
        pdf_bytes,
        now_iso(),
    )
    return {
        "content": pdf_bytes,
        "filename": filename,
        "mimetype": "application/pdf",
    }


def list_report_type_values():
    return [
        {"key": report_type, **definition}
        for report_type, definition in REPORT_DEFINITIONS.items()
        if report_type not in HIDDEN_REPORT_TYPE_OPTIONS
    ]


def list_report_type_keys():
    return list(REPORT_DEFINITIONS.keys())


def _parse_submission(form, files):
    name = (form.get("name") or "").strip()
    org = (form.get("org") or "").strip()
    report_type = (form.get("report_type") or "").strip()
    course_session = (form.get("course_session") or "").strip()
    score_date = (form.get("date") or "").strip()
    note = (form.get("note") or "").strip()
    transcript = (form.get("transcript") or "").strip()
    transcript_file = files.get("transcript_file")
    pdf_file = files.get("pdf_file")

    if not name:
        raise ApplicationError("missing_name", "Name is required.", 400)
    if not org:
        raise ApplicationError("missing_org", "Organization is required.", 400)
    if report_type not in REPORT_DEFINITIONS:
        raise ApplicationError("invalid_report_type", "A valid report type is required.", 400)
    if course_session not in COURSE_SESSION_OPTIONS:
        raise ApplicationError("invalid_course_session", "A valid course session is required.", 400)
    if not score_date:
        raise ApplicationError("missing_date", "Score date is required.", 400)
    if pdf_file is None or not pdf_file.filename:
        raise ApplicationError("missing_pdf", "A PDF file is required.", 400)
    if not pdf_file.filename.lower().endswith(".pdf"):
        raise ApplicationError("invalid_pdf", "Only PDF files are supported.", 400)

    pdf_bytes = pdf_file.read()
    if not pdf_bytes:
        raise ApplicationError("empty_pdf", "The uploaded PDF is empty.", 400)
    if len(pdf_bytes) > 20 * 1024 * 1024:
        raise ApplicationError("pdf_too_large", "The uploaded PDF must be smaller than 20MB.", 400)

    transcript_file_bytes = b""
    transcript_filename = ""
    if transcript_file is not None and getattr(transcript_file, "filename", ""):
        transcript_filename = transcript_file.filename
        transcript_file_bytes = transcript_file.read()
    transcript, transcript_filename = _resolve_transcript_input(
        transcript,
        transcript_filename,
        transcript_file_bytes,
    )

    return ScoreSubmissionInput(
        name=name,
        org=org,
        report_type=report_type,
        course_session=course_session,
        score_date=score_date,
        note=note,
        transcript=transcript,
        transcript_filename=transcript_filename,
        transcript_file_bytes=transcript_file_bytes,
        pdf_file=pdf_file,
        pdf_bytes=pdf_bytes,
    )


def _resolve_transcript_input(transcript_text, transcript_filename, transcript_file_bytes):
    normalized = transcript_text.strip()
    decoded_from_file = ""
    if transcript_file_bytes:
        decoded_from_file = _decode_transcript_bytes(transcript_file_bytes)

    if normalized and not looks_like_garbled_text(normalized):
        return normalized, transcript_filename if transcript_file_bytes else ""
    if decoded_from_file:
        return decoded_from_file, transcript_filename
    if normalized:
        return normalized, ""
    if not transcript_file_bytes:
        return "", ""

    return "", transcript_filename


def _decode_transcript_bytes(payload):
    if not payload:
        return ""
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            decoded = payload.decode(encoding).strip()
        except Exception:
            continue
        if decoded:
            return decoded

    raise ApplicationError(
        "invalid_transcript_file",
        "The uploaded transcript file could not be decoded as text.",
        400,
    )
