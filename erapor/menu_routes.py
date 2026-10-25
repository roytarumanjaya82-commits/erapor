from io import BytesIO

from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import generate_password_hash

from .access import ENDPOINT_TUGAS
from .auth import login_required
from .db import execute, query, transaction

bp = Blueprint("menu", __name__)

ENDPOINT_TUGAS.update(
    {
        "menu.audit": {"admin", "bidang_studi"},
        "menu.leger": {"admin", "walas", "bidang_studi"},
        "menu.cetak_rapor": {"admin", "walas"},
        "menu.rapor_siswa": {"admin", "walas"},
        "menu.publik": {"admin", "bidang_studi", "walas", "ekskul", "tahfidz"},
        "menu.dapodik": {"admin"},
        "menu.pengguna": {"admin"},
        "menu.tambah_pengguna": {"admin"},
        "menu.generate_guru": {"admin"},
        "menu.generate_siswa": {"admin"},
        "menu.kosongkan": {"admin"},
        "menu.backup": {"admin"},
        "menu.backup_unduh": {"admin"},
        "menu.restore": {"admin"},
        "menu.dimensi": {"admin", "walas"},
        "menu.hapus_dimensi": {"admin"},
        "menu.predikat": {"admin", "walas"},
        "menu.hapus_predikat": {"admin"},
        "menu.cetak_tahfiz": {"admin", "tahfidz", "walas"},
        "menu.nilai_mapel": {"admin", "bidang_studi"},
        "menu.simpan_nilai_mapel": {"admin", "bidang_studi"},
        "menu.nilai_ekskul": {"admin", "ekskul"},
        "menu.simpan_ekskul": {"admin", "ekskul"},
    }
)


def _ta_id():
    ta = query("SELECT id FROM tahun_ajaran WHERE aktif=1 LIMIT 1", one=True)
    return ta["id"] if ta else None


def _is_admin():
    return "admin" in set(session.get("tugas") or [])


def _guru_id():
    return session.get("guru_id")


def _kelas_scope():
    if _is_admin():
        return query(
            "SELECT id, nama FROM kelas ORDER BY FIELD(tingkat,'VII','VIII','IX','X','XI','XII'), nama"
        )
    gid = _guru_id()
    if not gid:
        return []
    tugas = set(session.get("tugas") or [])
    rows = []
    if "walas" in tugas:
        rows += query("SELECT id, nama FROM kelas WHERE wali_kelas_id=%s", (gid,))
    if "tahfidz" in tugas:
        rows += query(
            """SELECT DISTINCT k.id, k.nama FROM kelas k
               JOIN mapping_guru_tahfiz m ON m.kelas_id=k.id
               WHERE m.guru_id=%s""",
            (gid,),
        )
    if "bidang_studi" in tugas:
        rows += query(
            """SELECT DISTINCT k.id, k.nama FROM kelas k
               JOIN pelajaran p ON p.kelas_id=k.id
               WHERE p.guru_id=%s""",
            (gid,),
        )
    unik = {}
    for row in rows:
        unik[row["id"]] = row
    return list(unik.values())


@bp.route("/monitoring/publik")
@login_required
def publik():
    ta_id = _ta_id()
    pelajaran = query("SELECT COUNT(*) AS n FROM pelajaran WHERE tahun_ajaran_id=%s", (ta_id,), one=True)["n"] if ta_id else 0
    lengkap = query(
        """SELECT COUNT(*) AS n FROM pelajaran pel
           WHERE pel.tahun_ajaran_id=%s
             AND (SELECT COUNT(*) FROM siswa s WHERE s.kelas_id=pel.kelas_id AND s.status='aktif') > 0
             AND (SELECT COUNT(*) FROM nilai_sumatif ns WHERE ns.pelajaran_id=pel.id)
                 >= (SELECT COUNT(*) FROM siswa s WHERE s.kelas_id=pel.kelas_id AND s.status='aktif')""",
        (ta_id,),
        one=True,
    )["n"] if ta_id else 0
    stats = {
        "pelajaran": pelajaran,
        "lengkap": lengkap,
        "pct": round(lengkap * 100 / pelajaran) if pelajaran else 0,
        "guru": query("SELECT COUNT(*) AS n FROM guru WHERE aktif=1", one=True)["n"],
        "kelas": query("SELECT COUNT(*) AS n FROM kelas", one=True)["n"],
        "siswa": query("SELECT COUNT(*) AS n FROM siswa WHERE status='aktif'", one=True)["n"],
    }
    return render_template("menu/publik.html", stats=stats, nav="publik")


@bp.route("/admin/audit")
@login_required
def audit():
    ta_id = _ta_id()
    sql = """
        SELECT k.nama AS kelas_nama, m.nama AS mapel_nama, g.nama AS guru_nama,
               (SELECT COUNT(*) FROM siswa s WHERE s.kelas_id=pel.kelas_id AND s.status='aktif') AS siswa,
               (SELECT COUNT(*) FROM nilai_formatif nf WHERE nf.pelajaran_id=pel.id) AS formatif,
               (SELECT COUNT(*) FROM nilai_sumatif ns WHERE ns.pelajaran_id=pel.id) AS sumatif
        FROM pelajaran pel
        JOIN kelas k ON k.id=pel.kelas_id
        JOIN mata_pelajaran m ON m.id=pel.mapel_id
        JOIN guru g ON g.id=pel.guru_id
        WHERE pel.tahun_ajaran_id=%s
    """
    params = [ta_id]
    if not _is_admin():
        sql += " AND pel.guru_id=%s"
        params.append(_guru_id() or 0)
    sql += " ORDER BY k.nama, m.nama"
    rows = query(sql, params) if ta_id else []
    for row in rows:
        total = row["siswa"] or 0
        row["fmt"] = round(row["formatif"] * 100 / total) if total else 0
        row["sum"] = round(row["sumatif"] * 100 / total) if total else 0
        if total and row["formatif"] >= total and row["sumatif"] >= total:
            row["status"] = "Lengkap"
        elif row["formatif"] or row["sumatif"]:
            row["status"] = "Proses"
        else:
            row["status"] = "Belum mengisi"
    return render_template("menu/audit.html", rows=rows, nav="audit")


@bp.route("/admin/leger")
@login_required
def leger():
    kelas = _kelas_scope()
    boleh = {str(item["id"]) for item in kelas}
    minta = request.args.get("kelas_id") or ""
    kelas_id = minta if minta in boleh else (kelas[0]["id"] if kelas else "")
    siswa = []
    mapel = []
    if kelas_id:
        siswa = query(
            "SELECT id, nis, nisn, nama, jenis_kelamin FROM siswa WHERE kelas_id=%s AND status='aktif' ORDER BY nama",
            (kelas_id,),
        )
        mapel = query(
            """SELECT pel.id, m.nama FROM pelajaran pel
               JOIN mata_pelajaran m ON m.id=pel.mapel_id
               WHERE pel.kelas_id=%s ORDER BY m.nama""",
            (kelas_id,),
        )
        nilai = {
            (row["siswa_id"], row["pelajaran_id"]): row["nilai"]
            for row in query(
                """SELECT ns.siswa_id, ns.pelajaran_id, ns.nilai FROM nilai_sumatif ns
                   JOIN pelajaran pel ON pel.id=ns.pelajaran_id WHERE pel.kelas_id=%s""",
                (kelas_id,),
            )
        }
        for item in siswa:
            item["nilai"] = [nilai.get((item["id"], m["id"])) for m in mapel]
    info = query(
        """SELECT k.nama, k.tingkat, g.nama AS wali, COUNT(s.id) AS siswa
           FROM kelas k
           LEFT JOIN guru g ON g.id=k.wali_kelas_id
           LEFT JOIN siswa s ON s.kelas_id=k.id AND s.status='aktif'
           WHERE k.id=%s GROUP BY k.id""",
        (kelas_id,),
        one=True,
    ) if kelas_id else None
    return render_template(
        "menu/leger.html", kelas=kelas, kelas_id=str(kelas_id), siswa=siswa, mapel=mapel, info=info, nav="leger"
    )


@bp.route("/admin/cetak-rapor")
@login_required
def cetak_rapor():
    if _is_admin():
        kelas = _kelas_scope()
    else:
        kelas = query(
            "SELECT id, nama FROM kelas WHERE wali_kelas_id=%s ORDER BY nama",
            (_guru_id() or 0,),
        )
    boleh = {str(item["id"]) for item in kelas}
    kelas_id = request.args.get("kelas_id") or ""
    if str(kelas_id) not in boleh:
        kelas_id = ""
    siswa = query(
        "SELECT id, nis, nisn, nama, jenis_kelamin FROM siswa WHERE kelas_id=%s AND status='aktif' ORDER BY nama",
        (kelas_id,),
    ) if kelas_id else []
    return render_template("menu/cetak_rapor.html", kelas=kelas, kelas_id=str(kelas_id), siswa=siswa, nav="cetak")


@bp.route("/admin/cetak-rapor/<int:siswa_id>")
@login_required
def rapor_siswa(siswa_id):
    siswa = query(
        """SELECT s.*, k.nama AS kelas_nama, g.nama AS wali, g.gelar_belakang
           FROM siswa s LEFT JOIN kelas k ON k.id=s.kelas_id
           LEFT JOIN guru g ON g.id=k.wali_kelas_id WHERE s.id=%s""",
        (siswa_id,),
        one=True,
    )
    if not siswa:
        flash("Siswa tidak ditemukan.", "error")
        return redirect(url_for("menu.cetak_rapor"))
    if not _is_admin():
        milik = query(
            "SELECT id FROM kelas WHERE id=%s AND wali_kelas_id=%s",
            (siswa["kelas_id"], _guru_id() or 0),
            one=True,
        )
        if not milik:
            flash("Anda hanya dapat mencetak rapor kelas binaannya.", "error")
            return redirect(url_for("menu.cetak_rapor"))
    mapel = query(
        """SELECT m.nama, p.kkm, ns.nilai
           FROM pelajaran pel
           JOIN mata_pelajaran m ON m.id=pel.mapel_id
           LEFT JOIN perencanaan_penilaian p ON p.pelajaran_id=pel.id
           LEFT JOIN nilai_sumatif ns ON ns.pelajaran_id=pel.id AND ns.siswa_id=%s
           WHERE pel.kelas_id=%s ORDER BY m.nama""",
        (siswa_id, siswa["kelas_id"]),
    )
    ekskul = query(
        """SELECT e.nama, n.nilai FROM nilai_ekskul n
           JOIN ekstrakurikuler e ON e.id=n.ekskul_id WHERE n.siswa_id=%s""",
        (siswa_id,),
    )
    sekolah = query("SELECT * FROM sekolah LIMIT 1", one=True) or {}
    ta = query("SELECT * FROM tahun_ajaran WHERE aktif=1 LIMIT 1", one=True)
    return render_template("menu/rapor_siswa.html", siswa=siswa, mapel=mapel, ekskul=ekskul, sekolah=sekolah, ta=ta)


@bp.route("/admin/dapodik")
@login_required
def dapodik():
    return render_template("menu/dapodik.html", nav="dapodik")


@bp.route("/admin/pengguna", methods=["GET", "POST"])
@login_required
def pengguna():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        nama = (request.form.get("nama") or "").strip()
        password = request.form.get("password") or "guru123"
        guru_id = request.form.get("guru_id") or None
        tugas = request.form.getlist("tugas")
        if not username or not nama:
            flash("Username dan nama wajib diisi.", "error")
        else:
            try:
                uid = execute(
                    "INSERT INTO users (username, password_hash, nama, role, guru_id) VALUES (%s,%s,%s,'guru',%s)",
                    (username, generate_password_hash(password), nama, guru_id),
                )
                for item in tugas:
                    if item in {"bidang_studi", "walas", "ekskul", "tahfidz"}:
                        execute("INSERT INTO user_tugas (user_id, tugas) VALUES (%s,%s)", (uid, item))
                flash("Pengguna ditambahkan.", "success")
            except Exception:
                flash("Username sudah dipakai atau data tidak valid.", "error")
        return redirect(url_for("menu.pengguna"))
    tab = request.args.get("tab") or "guru"
    if tab == "admin":
        rows = query("SELECT * FROM users WHERE role='admin' ORDER BY nama")
    elif tab == "siswa":
        rows = query("SELECT * FROM users WHERE role='siswa' ORDER BY nama LIMIT 300")
    else:
        rows = query(
            """SELECT u.*, GROUP_CONCAT(t.tugas ORDER BY t.tugas SEPARATOR ', ') AS tugas_nama
               FROM users u LEFT JOIN user_tugas t ON t.user_id=u.id
               WHERE u.role<>'siswa' AND u.role<>'admin'
               GROUP BY u.id ORDER BY u.nama"""
        )
        tab = "guru"
    guru = query("SELECT id, nama FROM guru ORDER BY nama")
    return render_template("menu/pengguna.html", rows=rows, tab=tab, guru=guru, nav="pengguna")


@bp.route("/admin/pengguna/generate-guru", methods=["POST"])
@login_required
def generate_guru():
    dibuat = 0
    for guru in query("SELECT id, nama FROM guru"):
        username = "".join(ch for ch in guru["nama"].lower() if ch.isalnum())[:20] or f"guru{guru['id']}"
        if query("SELECT id FROM users WHERE username=%s OR guru_id=%s", (username, guru["id"]), one=True):
            continue
        execute(
            "INSERT INTO users (username, password_hash, nama, role, guru_id) VALUES (%s,%s,%s,'guru',%s)",
            (username, generate_password_hash("guru123"), guru["nama"], guru["id"]),
        )
        dibuat += 1
    flash(f"{dibuat} akun guru dibuat. Kata sandi awal: guru123. Atur tugas tiap guru setelah itu.", "success")
    return redirect(url_for("menu.pengguna"))


@bp.route("/admin/pengguna/generate-siswa", methods=["POST"])
@login_required
def generate_siswa():
    dibuat = 0
    for siswa in query("SELECT id, nis, nama FROM siswa WHERE status='aktif'"):
        username = f"siswa{siswa['nis']}"[:50]
        if query("SELECT id FROM users WHERE username=%s", (username,), one=True):
            continue
        execute(
            "INSERT INTO users (username, password_hash, nama, role) VALUES (%s,%s,%s,'siswa')",
            (username, generate_password_hash(str(siswa["nis"])), siswa["nama"]),
        )
        dibuat += 1
    flash(f"{dibuat} akun siswa dibuat. Username siswa+NIS, kata sandi sama dengan NIS.", "success")
    return redirect(url_for("menu.pengguna", tab="siswa"))


@bp.route("/admin/kosongkan", methods=["GET", "POST"])
@login_required
def kosongkan():
    if request.method == "POST":
        aksi = request.form.get("aksi")
        konfirmasi = (request.form.get("konfirmasi") or "").strip().upper()
        if aksi == "nilai" and konfirmasi == "KOSONGKAN":
            for table in ("nilai_formatif", "nilai_sumatif", "nilai_tahfiz", "nilai_ekskul"):
                execute(f"DELETE FROM {table}")
            flash("Data nilai dikosongkan.", "success")
        elif aksi == "reset" and konfirmasi == "RESET":
            execute("DELETE FROM nilai_formatif")
            execute("DELETE FROM nilai_sumatif")
            execute("DELETE FROM nilai_tahfiz")
            execute("DELETE FROM nilai_ekskul")
            execute("DELETE FROM pelajaran")
            execute("DELETE FROM siswa")
            execute("DELETE FROM kelas")
            execute("DELETE FROM ekstrakurikuler")
            execute("DELETE FROM users WHERE role<>'admin'")
            execute("DELETE FROM guru")
            flash("Data aplikasi dikosongkan. Akun admin tetap ada.", "success")
        else:
            flash("Ketik KOSONGKAN atau RESET sesuai tombol yang dipilih.", "error")
        return redirect(url_for("menu.kosongkan"))
    jumlah = {
        "nilai": query(
            """SELECT
                 (SELECT COUNT(*) FROM nilai_formatif) +
                 (SELECT COUNT(*) FROM nilai_sumatif) +
                 (SELECT COUNT(*) FROM nilai_tahfiz) AS n""",
            one=True,
        )["n"],
        "siswa": query("SELECT COUNT(*) AS n FROM siswa", one=True)["n"],
        "guru": query("SELECT COUNT(*) AS n FROM guru", one=True)["n"],
        "kelas": query("SELECT COUNT(*) AS n FROM kelas", one=True)["n"],
    }
    return render_template("menu/kosongkan.html", jumlah=jumlah, nav="kosongkan")


@bp.route("/admin/backup", methods=["GET"])
@login_required
def backup():
    return render_template("menu/backup.html", nav="backup")


@bp.route("/admin/backup/unduh")
@login_required
def backup_unduh():
    tables = [
        "sekolah", "tahun_ajaran", "guru", "kelas", "siswa", "kelompok_mapel", "mata_pelajaran",
        "pelajaran", "perencanaan_penilaian", "nilai_formatif", "nilai_sumatif", "ekstrakurikuler",
        "nilai_ekskul", "aspek_tahfiz", "mapping_guru_tahfiz", "nilai_tahfiz", "dimensi_sikap", "predikat_sikap",
    ]
    chunks = ["-- eRapor backup SMPM22SETIABUDIPAMULANG\nSET FOREIGN_KEY_CHECKS=0;\n"]
    for table in tables:
        try:
            rows = query(f"SELECT * FROM {table}")
        except Exception:
            continue
        chunks.append(f"DELETE FROM {table};\n")
        if not rows:
            continue
        cols = list(rows[0].keys())
        col_sql = ", ".join(f"`{col}`" for col in cols)
        for row in rows:
            vals = []
            for col in cols:
                value = row[col]
                if value is None:
                    vals.append("NULL")
                elif isinstance(value, (int, float)):
                    vals.append(str(value))
                else:
                    text = str(value).replace("\\", "\\\\").replace("'", "''")
                    vals.append(f"'{text}'")
            chunks.append(f"INSERT INTO {table} ({col_sql}) VALUES ({', '.join(vals)});\n")
    chunks.append("SET FOREIGN_KEY_CHECKS=1;\n")
    data = "".join(chunks).encode("utf-8")
    return send_file(BytesIO(data), as_attachment=True, download_name="erapor-backup.sql", mimetype="application/sql")


@bp.route("/admin/backup/restore", methods=["POST"])
@login_required
def restore():
    berkas = request.files.get("berkas")
    if not berkas or not berkas.filename:
        flash("Pilih file backup .sql hasil unduhan aplikasi ini.", "error")
        return redirect(url_for("menu.backup"))
    text = berkas.read().decode("utf-8", "replace")
    if not text.startswith("-- eRapor backup"):
        flash("File bukan backup eRapor yang dikenali.", "error")
        return redirect(url_for("menu.backup"))
    with transaction():
        for statement in text.split(";"):
            sql = statement.strip()
            if sql and not sql.startswith("--"):
                execute(sql)
    flash("Backup berhasil dipulihkan.", "success")
    return redirect(url_for("menu.backup"))


@bp.route("/admin/dimensi-sikap", methods=["GET", "POST"])
@login_required
def dimensi():
    if request.method == "POST" and _is_admin():
        execute(
            "INSERT INTO dimensi_sikap (nama, indikator, kelas_7, kelas_8, kelas_9, urutan) VALUES (%s,%s,%s,%s,%s,%s)",
            (
                request.form.get("nama"),
                request.form.get("indikator"),
                1 if request.form.get("kelas_7") else 0,
                1 if request.form.get("kelas_8") else 0,
                1 if request.form.get("kelas_9") else 0,
                int(request.form.get("urutan") or 0),
            ),
        )
        flash("Dimensi sikap ditambahkan.", "success")
        return redirect(url_for("menu.dimensi"))
    rows = query("SELECT * FROM dimensi_sikap ORDER BY urutan, id")
    return render_template("menu/dimensi.html", rows=rows, nav="dimensi")


@bp.route("/admin/dimensi-sikap/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_dimensi(item_id):
    execute("DELETE FROM dimensi_sikap WHERE id=%s", (item_id,))
    flash("Dimensi sikap dihapus.", "success")
    return redirect(url_for("menu.dimensi"))


@bp.route("/admin/predikat-sikap", methods=["GET", "POST"])
@login_required
def predikat():
    if request.method == "POST" and _is_admin():
        execute(
            "INSERT INTO predikat_sikap (nama, deskripsi, urutan, aktif) VALUES (%s,%s,%s,1)",
            (request.form.get("nama"), request.form.get("deskripsi"), int(request.form.get("urutan") or 0)),
        )
        flash("Predikat sikap ditambahkan.", "success")
        return redirect(url_for("menu.predikat"))
    rows = query("SELECT * FROM predikat_sikap ORDER BY urutan, id")
    return render_template("menu/predikat.html", rows=rows, nav="predikat")


@bp.route("/admin/predikat-sikap/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_predikat(item_id):
    execute("DELETE FROM predikat_sikap WHERE id=%s", (item_id,))
    flash("Predikat dihapus.", "success")
    return redirect(url_for("menu.predikat"))


@bp.route("/admin/cetak-tahfiz")
@login_required
def cetak_tahfiz():
    kelas = _kelas_scope() if not _is_admin() else query("SELECT id, nama FROM kelas ORDER BY nama")
    boleh = {str(item["id"]) for item in kelas}
    kelas_id = request.args.get("kelas_id") or ""
    if str(kelas_id) not in boleh:
        kelas_id = ""
    siswa = []
    if kelas_id:
        siswa = query(
            """SELECT s.id, s.nama, s.nis, a.nama AS aspek, n.nilai, n.predikat
               FROM siswa s
               LEFT JOIN nilai_tahfiz n ON n.siswa_id=s.id
               LEFT JOIN aspek_tahfiz a ON a.id=n.aspek_id
               WHERE s.kelas_id=%s AND s.status='aktif'
               ORDER BY s.nama, a.nama""",
            (kelas_id,),
        )
    return render_template("menu/cetak_tahfiz.html", kelas=kelas, kelas_id=str(kelas_id), siswa=siswa, nav="cetaktahfiz")


def _pelajaran_tugas():
    ta_id = _ta_id()
    if not ta_id:
        return []
    sql = """
        SELECT pel.id, k.nama AS kelas_nama, m.nama AS mapel_nama
        FROM pelajaran pel
        JOIN kelas k ON k.id=pel.kelas_id
        JOIN mata_pelajaran m ON m.id=pel.mapel_id
        WHERE pel.tahun_ajaran_id=%s
    """
    params = [ta_id]
    if not _is_admin():
        sql += " AND pel.guru_id=%s"
        params.append(_guru_id() or 0)
    sql += " ORDER BY k.nama, m.nama"
    return query(sql, params)


def _angka_nilai(value):
    teks = "" if value is None else str(value).strip()
    if teks == "":
        return ""
    try:
        angka = float(teks.replace(",", "."))
    except ValueError:
        return None
    if angka < 0 or angka > 100:
        return None
    return round(angka, 2)


@bp.route("/admin/nilai-mapel", methods=["GET"])
@login_required
def nilai_mapel():
    pelajaran = _pelajaran_tugas()
    milik = {str(item["id"]) for item in pelajaran}
    pelajaran_id = request.args.get("pelajaran_id") or (pelajaran[0]["id"] if pelajaran else "")
    if str(pelajaran_id) not in milik:
        pelajaran_id = ""
    siswa = []
    if pelajaran_id:
        siswa = query(
            """SELECT s.id, s.nis, s.nama, nf.nilai AS formatif, ns.nilai AS sumatif
               FROM pelajaran pel
               JOIN siswa s ON s.kelas_id=pel.kelas_id AND s.status='aktif'
               LEFT JOIN nilai_formatif nf ON nf.pelajaran_id=pel.id AND nf.siswa_id=s.id
               LEFT JOIN nilai_sumatif ns ON ns.pelajaran_id=pel.id AND ns.siswa_id=s.id
               WHERE pel.id=%s
               ORDER BY s.nama""",
            (pelajaran_id,),
        )
        for item in siswa:
            for kolom in ("formatif", "sumatif"):
                if item[kolom] is None:
                    item[kolom] = ""
                else:
                    teks = format(item[kolom], "f").rstrip("0").rstrip(".")
                    item[kolom] = teks
    return render_template(
        "menu/nilai_mapel.html",
        pelajaran=pelajaran,
        pelajaran_id=str(pelajaran_id),
        siswa=siswa,
        nav="nilaimapel",
    )


@bp.route("/admin/nilai-mapel/simpan", methods=["POST"])
@login_required
def simpan_nilai_mapel():
    pelajaran_id = request.form.get("pelajaran_id")
    boleh = {str(item["id"]) for item in _pelajaran_tugas()}
    if str(pelajaran_id) not in boleh:
        flash("Pembelajaran ini bukan tugas Anda.", "error")
        return redirect(url_for("menu.nilai_mapel"))
    ids = request.form.getlist("siswa_id")
    siap = []
    for sid in ids:
        for kolom, tabel in (("formatif", "nilai_formatif"), ("sumatif", "nilai_sumatif")):
            angka = _angka_nilai(request.form.get(f"{kolom}_{sid}"))
            if angka is None:
                flash("Nilai harus angka antara 0 dan 100.", "error")
                return redirect(url_for("menu.nilai_mapel", pelajaran_id=pelajaran_id))
            siap.append((tabel, sid, angka))
    with transaction():
        for tabel, sid, angka in siap:
            if angka == "":
                execute(f"DELETE FROM {tabel} WHERE pelajaran_id=%s AND siswa_id=%s", (pelajaran_id, sid))
            else:
                execute(
                    f"""INSERT INTO {tabel} (pelajaran_id, siswa_id, nilai) VALUES (%s,%s,%s)
                        ON DUPLICATE KEY UPDATE nilai=VALUES(nilai)""",
                    (pelajaran_id, sid, angka),
                )
    flash("Nilai mapel disimpan.", "success")
    return redirect(url_for("menu.nilai_mapel", pelajaran_id=pelajaran_id))


@bp.route("/admin/nilai-ekskul", methods=["GET"])
@login_required
def nilai_ekskul():
    if _is_admin():
        ekskul = query("SELECT id, nama FROM ekstrakurikuler ORDER BY nama")
    else:
        ekskul = query("SELECT id, nama FROM ekstrakurikuler WHERE pembina_id=%s ORDER BY nama", (_guru_id() or 0,))
    milik = {str(item["id"]) for item in ekskul}
    ekskul_id = request.args.get("ekskul_id") or (ekskul[0]["id"] if ekskul else "")
    if str(ekskul_id) not in milik:
        ekskul_id = ""
    kelas = query("SELECT id, nama FROM kelas ORDER BY nama")
    kelas_id = request.args.get("kelas_id") or ""
    siswa = []
    if ekskul_id and kelas_id:
        siswa = query(
            """SELECT s.id, s.nama, s.nis, n.nilai
               FROM siswa s
               LEFT JOIN nilai_ekskul n ON n.siswa_id=s.id AND n.ekskul_id=%s
               WHERE s.kelas_id=%s AND s.status='aktif' ORDER BY s.nama""",
            (ekskul_id, kelas_id),
        )
    return render_template(
        "menu/nilai_ekskul.html",
        ekskul=ekskul,
        ekskul_id=str(ekskul_id),
        kelas=kelas,
        kelas_id=str(kelas_id),
        siswa=siswa,
        nav="nilaiekskul",
    )


@bp.route("/admin/nilai-ekskul/simpan", methods=["POST"])
@login_required
def simpan_ekskul():
    ekskul_id = request.form.get("ekskul_id")
    kelas_id = request.form.get("kelas_id")
    if not _is_admin():
        milik = query(
            "SELECT id FROM ekstrakurikuler WHERE id=%s AND pembina_id=%s",
            (ekskul_id, _guru_id() or 0),
            one=True,
        )
        if not milik:
            flash("Ekstrakurikuler ini bukan binaannya.", "error")
            return redirect(url_for("menu.nilai_ekskul"))
    for sid in request.form.getlist("siswa_id"):
        nilai = (request.form.get(f"nilai_{sid}") or "").strip()
        if not nilai:
            continue
        execute(
            """INSERT INTO nilai_ekskul (ekskul_id, siswa_id, nilai) VALUES (%s,%s,%s)
               ON DUPLICATE KEY UPDATE nilai=VALUES(nilai)""",
            (ekskul_id, sid, nilai),
        )
    flash("Nilai ekstrakurikuler disimpan.", "success")
    return redirect(url_for("menu.nilai_ekskul", ekskul_id=ekskul_id, kelas_id=kelas_id))
