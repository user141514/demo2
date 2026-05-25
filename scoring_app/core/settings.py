import os


def configure_app(app):
    app.config.setdefault("JSON_AS_ASCII", False)
    app.config.setdefault(
        "AUTH_COOKIE_NAME", os.getenv("SCORING_APP_AUTH_COOKIE_NAME", "scoring_session")
    )
    app.config.setdefault(
        "AUTH_SESSION_DAYS", int(os.getenv("SCORING_APP_AUTH_SESSION_DAYS", "7"))
    )
    app.config.setdefault(
        "AUTH_COOKIE_SECURE",
        _is_truthy(os.getenv("SCORING_APP_AUTH_COOKIE_SECURE", "0")),
    )
    app.config.setdefault(
        "SMTP_HOST", (os.getenv("SCORING_APP_SMTP_HOST") or "").strip()
    )
    app.config.setdefault(
        "SMTP_PORT", int(os.getenv("SCORING_APP_SMTP_PORT", "587"))
    )
    app.config.setdefault(
        "SMTP_USERNAME", (os.getenv("SCORING_APP_SMTP_USERNAME") or "").strip()
    )
    app.config.setdefault(
        "SMTP_PASSWORD", os.getenv("SCORING_APP_SMTP_PASSWORD", "")
    )
    app.config.setdefault(
        "SMTP_FROM", (os.getenv("SCORING_APP_SMTP_FROM") or "").strip()
    )
    app.config.setdefault(
        "SMTP_USE_TLS", _is_truthy(os.getenv("SCORING_APP_SMTP_USE_TLS", "1"))
    )
    app.config.setdefault(
        "SMTP_SUPPRESS_SEND",
        _is_truthy(os.getenv("SCORING_APP_SMTP_SUPPRESS_SEND", "0")),
    )
    app.config.setdefault(
        "EXPOSE_RESET_TOKENS",
        _is_truthy(os.getenv("SCORING_APP_EXPOSE_RESET_TOKENS", "0")),
    )
    app.config.setdefault(
        "APP_BASE_URL", (os.getenv("SCORING_APP_APP_BASE_URL") or "").strip()
    )


def _is_truthy(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
