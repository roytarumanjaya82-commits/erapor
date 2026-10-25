from flask import Flask, g, session
from .config import Config
from .db import init_app, query


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(Config)
    init_app(app)

    from .auth import bp as auth_bp
    from .routes import bp as main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    @app.context_processor
    def inject_globals():
        user = None
        if session.get("user_id"):
            user = {
                "id": session["user_id"],
                "nama": session.get("nama"),
                "role": session.get("role"),
                "username": session.get("username"),
            }
        ta = None
        try:
            ta = query("SELECT * FROM tahun_ajaran WHERE aktif=1 LIMIT 1", one=True)
        except Exception:
            ta = None
        return {"current_user": user, "tahun_aktif": ta}

    return app
