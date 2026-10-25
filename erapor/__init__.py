import pymysql
from flask import Flask, flash, redirect, request, session, url_for
from .config import Config
from .db import init_app, query


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(Config)
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024
    init_app(app)

    from .access import TUGAS_LABEL, guard_request, load_tugas
    from .auth import bp as auth_bp
    from .menu_routes import bp as menu_bp
    from .routes import InputError, bp as main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(menu_bp)
    app.before_request(guard_request)

    @app.context_processor
    def inject_globals():
        user = None
        tugas = set()
        if session.get("user_id"):
            tugas = load_tugas()
            user = {
                "id": session["user_id"],
                "nama": session.get("nama"),
                "role": session.get("role"),
                "username": session.get("username"),
                "guru_id": session.get("guru_id"),
            }
        ta = None
        try:
            ta = query("SELECT * FROM tahun_ajaran WHERE aktif=1 LIMIT 1", one=True)
        except Exception:
            ta = None
        return {
            "current_user": user,
            "tahun_aktif": ta,
            "tugas": tugas,
            "tugas_label": TUGAS_LABEL,
        }

    def _back():
        ref = request.referrer or ""
        if ref.startswith(request.host_url):
            return redirect(ref)
        return redirect(url_for("main.dashboard"))

    @app.errorhandler(pymysql.err.IntegrityError)
    def handle_integrity(_e):
        flash("Data tidak bisa disimpan karena bentrok atau masih terkait data lain.", "error")
        return _back()

    @app.errorhandler(pymysql.err.DataError)
    def handle_data(_e):
        flash("Format data tidak valid. Periksa angka, tanggal, dan panjang isian.", "error")
        return _back()

    @app.errorhandler(413)
    def handle_large(_e):
        flash("Ukuran file maksimal 100MB.", "error")
        return _back()

    @app.errorhandler(InputError)
    def handle_value(_e):
        flash("Ada nilai yang bukan angka antara 0 dan 100.", "error")
        return _back()

    @app.template_filter("iso")
    def iso_date(value):
        if not value:
            return ""
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")
        return str(value)[:10]

    @app.template_filter("iddate")
    def id_date(value):
        bulan = (
            "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember",
        )
        if not value or not hasattr(value, "day"):
            return ""
        return f"{value.day} {bulan[value.month]} {value.year}"

    @app.template_filter("idstamp")
    def id_stamp(value):
        singkat = (
            "", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
            "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
        )
        if not value or not hasattr(value, "day"):
            return ""
        return f"{value.day:02d} {singkat[value.month]} {value.year} {value.strftime('%H:%M')}"

    return app
