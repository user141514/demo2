from .auth import auth_bp
from .meta import meta_bp
from .pages import pages_bp
from .scores import scores_bp


def register_blueprints(app):
    app.register_blueprint(pages_bp)
    app.register_blueprint(meta_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(scores_bp)


__all__ = ["register_blueprints"]
