import pymysql
from flask import current_app, g


def get_conn():
    if "db" not in g:
        g.db = pymysql.connect(
            host=current_app.config["MYSQL_HOST"],
            port=current_app.config["MYSQL_PORT"],
            user=current_app.config["MYSQL_USER"],
            password=current_app.config["MYSQL_PASSWORD"],
            database=current_app.config["MYSQL_DATABASE"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )
    return g.db


def query(sql, params=None, one=False):
    with get_conn().cursor() as cur:
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        return rows[0] if one and rows else (rows if not one else None)


def execute(sql, params=None):
    with get_conn().cursor() as cur:
        cur.execute(sql, params or ())
        return cur.lastrowid


def execute_many(sql, seq):
    with get_conn().cursor() as cur:
        cur.executemany(sql, seq)


def close_db(_e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
