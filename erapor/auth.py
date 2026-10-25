from functools import wraps
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from .db import execute, query

bp = Blueprint("auth", __name__)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login"))
        return fn(*args, **kwargs)

    return wrapper


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        from .access import ensure_access

        ensure_access()
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = query("SELECT * FROM users WHERE username=%s", (username,), one=True)
        if user and user.get("aktif") == 0:
            flash("Akun ini tidak aktif.", "error")
        elif user and check_password_hash(user["password_hash"], password):
            execute(
                "UPDATE users SET login_terakhir=NOW(), ip_address=%s, sedang_login=1 WHERE id=%s",
                ((request.remote_addr or "")[:45], user["id"]),
            )
            session.clear()
            session["user_id"] = user["id"]
            session["nama"] = user["nama"]
            session["role"] = user["role"]
            session["username"] = user["username"]
            return redirect(url_for("main.dashboard"))
        else:
            flash("Username atau kata sandi salah.", "error")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    from .access import ensure_access

    ensure_access()
    user_id = session.get("user_id")
    session.clear()
    if user_id:
        execute("UPDATE users SET sedang_login=0 WHERE id=%s", (user_id,))
    return redirect(url_for("auth.login"))
