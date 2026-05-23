from flask import Flask, g, jsonify, render_template, request, send_file

from .auth import (
    AuthError,
    clear_session_cookie,
    configure_auth,
    create_password_reset,
    error_response,
    load_current_user,
    login_user,
    logout_current_session,
    password_reset_delivery_available,
    register_user,
    require_auth,
    reset_password,
    set_session_cookie,
)
from .database import init_storage
from .llm_config import get_public_llm_status
from .markdown_export import build_markdown
from .pdf_extract import PdfExtractionError, extract_text_from_pdf_bytes
from .repository import get_score_detail, init_db, list_scores, store_score
from .rules import REPORT_DEFINITIONS
from .scoring import ScoringError, score_submission
from .utils import save_upload


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    configure_auth(app)
    init_storage()
    init_db()

    @app.before_request
    def populate_current_user():
        load_current_user()

    def send_download(path, filename, mimetype):
        kwargs = {"mimetype": mimetype, "as_attachment": True}
        try:
            return send_file(str(path), download_name=filename, **kwargs)
        except TypeError:
            return send_file(str(path), attachment_filename=filename, **kwargs)

    def read_json():
        return request.get_json(silent=True) or {}

    def build_auth_response(user, token=None, status_code=200):
        response = jsonify({"user": user})
        response.status_code = status_code
        if token:
            set_session_cookie(response, token)
        return response

    @app.route("/", methods=["GET"])
    def index():
        return render_template("index.html", report_types=list(REPORT_DEFINITIONS.keys()))

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify(
            {
                "status": "ok",
                "llm": get_public_llm_status(),
                "auth": {
                    "cookie_name": app.config["AUTH_COOKIE_NAME"],
                    "password_reset_mail_ready": password_reset_delivery_available(),
                    "smtp_suppressed": app.config["SMTP_SUPPRESS_SEND"],
                },
            }
        )

    @app.route("/api/report-types", methods=["GET"])
    def report_types():
        return jsonify({"items": list(REPORT_DEFINITIONS.values())})

    @app.route("/api/auth/register", methods=["POST"])
    def auth_register():
        try:
            user, token = register_user(read_json())
        except AuthError as exc:
            return error_response(exc.code, exc.message, exc.status_code)
        return build_auth_response(user, token=token, status_code=201)

    @app.route("/api/auth/login", methods=["POST"])
    def auth_login():
        try:
            user, token = login_user(read_json())
        except AuthError as exc:
            return error_response(exc.code, exc.message, exc.status_code)
        return build_auth_response(user, token=token)

    @app.route("/api/auth/logout", methods=["POST"])
    def auth_logout():
        logout_current_session()
        response = jsonify({"ok": True})
        return clear_session_cookie(response)

    @app.route("/api/auth/me", methods=["GET"])
    def auth_me():
        if g.get("current_user") is None:
            response, status_code = error_response(
                "auth_required", "当前未登录。", 401
            )
            response.status_code = status_code
            return clear_session_cookie(response)
        return jsonify({"user": g.current_user})

    @app.route("/api/auth/forgot-password", methods=["POST"])
    def auth_forgot_password():
        try:
            create_password_reset(read_json())
        except AuthError as exc:
            return error_response(exc.code, exc.message, exc.status_code)
        except Exception:
            app.logger.exception("Failed to send password reset mail")
            return jsonify(
                {
                    "ok": True,
                    "message": "如果该邮箱已注册，系统会向该邮箱发送密码重置邮件。",
                }
            )
        return jsonify(
            {
                "ok": True,
                "message": "如果该邮箱已注册，系统会向该邮箱发送密码重置邮件。",
            }
        )

    @app.route("/api/auth/reset-password", methods=["POST"])
    def auth_reset_password():
        try:
            reset_password(read_json())
        except AuthError as exc:
            return error_response(exc.code, exc.message, exc.status_code)
        response = jsonify({"ok": True})
        return clear_session_cookie(response)

    @app.route("/api/score", methods=["POST"])
    @require_auth
    def create_score():
        name = (request.form.get("name") or "").strip()
        org = (request.form.get("org") or "").strip()
        report_type = (request.form.get("report_type") or "").strip()
        score_date = (request.form.get("date") or "").strip()
        note = (request.form.get("note") or "").strip()
        transcript = (request.form.get("transcript") or "").strip()
        pdf_file = request.files.get("pdf_file")

        if not name:
            return jsonify({"error": "missing_name", "message": "请填写被评价人姓名。"}), 400
        if not org:
            return jsonify({"error": "missing_org", "message": "请填写所属组织或部门。"}), 400
        if report_type not in REPORT_DEFINITIONS:
            return jsonify({"error": "invalid_report_type", "message": "请选择有效的汇报类型。"}), 400
        if not score_date:
            return jsonify({"error": "missing_date", "message": "请选择评分日期。"}), 400
        if pdf_file is None or not pdf_file.filename:
            return jsonify({"error": "missing_pdf", "message": "请上传 PDF 文件。"}), 400
        if not pdf_file.filename.lower().endswith(".pdf"):
            return jsonify({"error": "invalid_pdf", "message": "仅支持 PDF 文件。"}), 400

        pdf_bytes = pdf_file.read()
        if not pdf_bytes:
            return jsonify({"error": "empty_pdf", "message": "上传的 PDF 文件为空。"}), 400
        if len(pdf_bytes) > 20 * 1024 * 1024:
            return jsonify({"error": "pdf_too_large", "message": "PDF 文件需小于 20MB。"}), 400

        try:
            document_text = extract_text_from_pdf_bytes(pdf_bytes)
        except PdfExtractionError as exc:
            return jsonify({"error": "pdf_extract_failed", "message": str(exc)}), 422

        try:
            upload_path = save_upload(pdf_file.filename, pdf_bytes)
            result = score_submission(
                report_type=report_type,
                document_text=document_text,
                transcript_text=transcript,
                metadata={
                    "name": name,
                    "org": org,
                    "date": score_date,
                    "note": note,
                    "pdf_filename": pdf_file.filename,
                    "upload_path": str(upload_path),
                    "document_preview": document_text[:800],
                },
            )
        except ScoringError as exc:
            return jsonify({"error": "score_failed", "message": str(exc)}), 422

        result["user_id"] = g.current_user["user_id"]
        result["markdown_content"] = build_markdown(result)
        result["markdown_export_url"] = "/api/scores/{}/export?format=md".format(
            result["score_id"]
        )
        store_score(result)
        result.pop("markdown_content", None)
        return jsonify(result)

    @app.route("/api/scores", methods=["GET"])
    @require_auth
    def scores():
        return jsonify(list_scores(g.current_user["user_id"]))

    @app.route("/api/scores/<score_id>", methods=["GET"])
    @require_auth
    def score_detail(score_id):
        detail = get_score_detail(score_id, g.current_user["user_id"])
        if detail is None:
            return jsonify({"error": "score_not_found", "message": "未找到对应评分记录。"}), 404
        return jsonify(detail)

    @app.route("/api/scores/<score_id>/export", methods=["GET"])
    @require_auth
    def export_markdown(score_id):
        export_format = (request.args.get("format") or "md").lower()
        if export_format != "md":
            return jsonify({"error": "invalid_export_format", "message": "当前仅支持导出 Markdown。"}), 400

        detail = get_score_detail(score_id, g.current_user["user_id"])
        if detail is None:
            return jsonify({"error": "score_not_found", "message": "未找到对应评分记录。"}), 404

        markdown = build_markdown(detail)
        filename = "{}_{}_{}.md".format(
            detail["name"], detail["report_type"], detail["date"]
        )
        file_path = save_upload(filename, markdown.encode("utf-8"), folder_name="exports")
        return send_download(file_path, filename, "text/markdown; charset=utf-8")

    return app
