import os

from scoring_app import create_app


app = create_app()


if __name__ == "__main__":
    debug = os.getenv("SCORING_APP_DEBUG", "0").strip().lower() in {"1", "true", "yes", "on"}
    host = os.getenv("SCORING_APP_HOST", "127.0.0.1")
    port = int(os.getenv("SCORING_APP_PORT", "5000"))
    app.run(debug=debug, host=host, port=port)
