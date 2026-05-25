from dataclasses import dataclass

from ..core.errors import ApplicationError
from ..markdown_export import build_markdown
from ..pdf_export import PdfBuildError, build_pdf_bytes
from ..pdf_extract import PdfExtractionError, extract_text_from_pdf_bytes
from ..repository import get_score_detail, list_scores, store_score
from ..rules import REPORT_DEFINITIONS
from ..scoring import ScoringError, score_submission
from ..utils import save_upload


@dataclass
class ScoreSubmissionInput:
    name: str
    org: str
    report_type: str
    score_date: str
    note: str
    transcript: str
    transcript_filename: str
    pdf_file: object
    pdf_bytes: bytes


def create_score(form, files, user_id):
    submission = _parse_submission(form, files)

    try:
        document_text = extract_text_from_pdf_bytes(submission.pdf_bytes)
    except PdfExtractionError as exc:
        raise ApplicationError("pdf_extract_failed", str(exc), 422)

    try:
        upload_path = save_upload(submission.pdf_file.filename, submission.pdf_bytes)
        result = score_submission(
            report_type=submission.report_type,
            document_text=document_text,
            transcript_text=submission.transcript,
            metadata={
                "name": submission.name,
                "org": submission.org,
                "date": submission.score_date,
                "note": submission.note,
                "pdf_filename": submission.pdf_file.filename,
                "upload_path": str(upload_path),
                "document_preview": document_text[:800],
            },
        )
    except ScoringError as exc:
        raise ApplicationError("score_failed", str(exc), 422)

    result["user_id"] = user_id
    result["markdown_export_url"] = "/api/scores/{}/export?format=md".format(
        result["score_id"]
    )
    result["pdf_export_url"] = "/api/scores/{}/export?format=pdf".format(
        result["score_id"]
    )
    store_score(result)
    return result


def list_user_scores(user_id):
    return list_scores(user_id)


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

    if export_format == "md":
        markdown = build_markdown(detail)
        filename = "{}.md".format(base_name)
        file_path = save_upload(filename, markdown.encode("utf-8"), folder_name="exports")
        return {
            "file_path": file_path,
            "filename": filename,
            "mimetype": "text/markdown; charset=utf-8",
        }

    try:
        pdf_bytes = build_pdf_bytes(detail)
    except PdfBuildError as exc:
        raise ApplicationError("pdf_export_failed", str(exc), 500)

    filename = "{}.pdf".format(base_name)
    file_path = save_upload(filename, pdf_bytes, folder_name="exports")
    return {
        "file_path": file_path,
        "filename": filename,
        "mimetype": "application/pdf",
    }


def list_report_type_values():
    return list(REPORT_DEFINITIONS.values())


def list_report_type_keys():
    return list(REPORT_DEFINITIONS.keys())


def _parse_submission(form, files):
    name = (form.get("name") or "").strip()
    org = (form.get("org") or "").strip()
    report_type = (form.get("report_type") or "").strip()
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

    transcript, transcript_filename = _resolve_transcript_input(transcript, transcript_file)

    return ScoreSubmissionInput(
        name=name,
        org=org,
        report_type=report_type,
        score_date=score_date,
        note=note,
        transcript=transcript,
        transcript_filename=transcript_filename,
        pdf_file=pdf_file,
        pdf_bytes=pdf_bytes,
    )


def _resolve_transcript_input(transcript_text, transcript_file):
    normalized = transcript_text.strip()
    if normalized:
        return normalized, ""

    if transcript_file is None or not getattr(transcript_file, "filename", ""):
        return "", ""

    payload = transcript_file.read()
    if not payload:
        return "", transcript_file.filename

    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            decoded = payload.decode(encoding).strip()
        except Exception:
            continue
        if decoded:
            return decoded, transcript_file.filename

    raise ApplicationError(
        "invalid_transcript_file",
        "The uploaded transcript file could not be decoded as text.",
        400,
    )
