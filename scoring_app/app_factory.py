from flask import Flask

from .blueprints import register_blueprints
from .core import bootstrap_runtime, configure_app, load_current_user


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    configure_app(app)
    bootstrap_runtime()
    app.before_request(load_current_user)
    register_blueprints(app)
    return app
