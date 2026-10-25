from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from .auth import login_required
from .db import execute, query, transaction
from .guru_excel import parse_guru_file, replace_guru

class InputError(ValueError):
    pass


bp = Blueprint("main", __name__)

ORDER_KELAS = (
    "FIELD(tingkat,'VII','VIII','IX','X','XI','XII'), "
    "CAST(SUBSTRING_INDEX(nama,'-',-1) AS UNSIGNED), nama"
)
ORDER_KELAS_K = (
    "FIELD(k.tingkat,'VII','VIII','IX','X','XI','XII'), "
    "CAST(SUBSTRING_INDEX(k.nama,'-',-1) AS UNSIGNED), k.nama"
)


def clean_date(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return value


def clean_nilai(value):
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if number < 0 or number > 100:
        return None
    return number


def to_int(value, default):
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _missing(row, endpoint):
    if row:
        return None
    flash("Data tidak ditemukan.", "error")
    return redirect(url_for(endpoint))


def _in_use(sql, params, message, endpoint):
    used = query(sql, params, one=True)["n"]
    if used:
        flash(message, "error")
        return redirect(url_for(endpoint))
    return None


def _ta_id():
    ta = query("SELECT id FROM tahun_ajaran WHERE aktif=1 LIMIT 1", one=True)
    return ta["id"] if ta else None


@bp.route("/")
def index():
    return redirect(url_for("main.dashboard"))


@bp.route("/admin")
@login_required
def dashboard():
    ta_id = _ta_id()
    stats = {
        "rombel": query("SELECT COUNT(*) AS n FROM kelas WHERE tahun_ajaran_id=%s", (ta_id,), one=True)["n"] if ta_id else 0,
        "siswa": query("SELECT COUNT(*) AS n FROM siswa WHERE status='aktif'", one=True)["n"],
        "guru": query("SELECT COUNT(*) AS n FROM guru WHERE aktif=1", one=True)["n"],
        "pelajaran": query("SELECT COUNT(*) AS n FROM pelajaran WHERE tahun_ajaran_id=%s", (ta_id,), one=True)["n"] if ta_id else 0,
    }
    mapped = query(
        "SELECT COUNT(*) AS n FROM perencanaan_penilaian p JOIN pelajaran pel ON pel.id=p.pelajaran_id WHERE pel.tahun_ajaran_id=%s AND p.mapped=1",
        (ta_id,),
        one=True,
    )["n"] if ta_id else 0
    expected_nilai = query(
        """
        SELECT COUNT(*) AS n
        FROM pelajaran pel
        JOIN siswa s ON s.kelas_id = pel.kelas_id AND s.status='aktif'
        WHERE pel.tahun_ajaran_id=%s
        """,
        (ta_id,),
        one=True,
    )["n"] if ta_id else 0
    isi_f = query(
        """
        SELECT COUNT(*) AS n FROM nilai_formatif nf
        JOIN pelajaran pel ON pel.id=nf.pelajaran_id
        WHERE pel.tahun_ajaran_id=%s
        """,
        (ta_id,),
        one=True,
    )["n"] if ta_id else 0
    isi_s = query(
        """
        SELECT COUNT(*) AS n FROM nilai_sumatif ns
        JOIN pelajaran pel ON pel.id=ns.pelajaran_id
        WHERE pel.tahun_ajaran_id=%s
        """,
        (ta_id,),
        one=True,
    )["n"] if ta_id else 0

    def pct(a, b):
        return round(a * 100 / b) if b else 0

    progress = {
        "rencana_done": mapped,
        "rencana_total": stats["pelajaran"],
        "rencana_pct": pct(mapped, stats["pelajaran"]),
        "formatif_done": isi_f,
        "formatif_total": expected_nilai,
        "formatif_pct": pct(isi_f, expected_nilai),
        "sumatif_done": isi_s,
        "sumatif_total": expected_nilai,
        "sumatif_pct": pct(isi_s, expected_nilai),
    }
    return render_template("dashboard.html", stats=stats, progress=progress, nav="dashboard")


# ---------- Sekolah ----------
@bp.route("/admin/sekolah", methods=["GET", "POST"])
@login_required
def data_sekolah():
    if request.method == "POST":
        fields = [
            "nama", "npsn", "jenjang", "alamat", "kelurahan", "kecamatan",
            "kabupaten", "provinsi", "kode_pos", "telepon", "email", "website",
            "kepala_sekolah", "nip_kepala",
        ]
        vals = [request.form.get(f) or None for f in fields]
        row = query("SELECT id FROM sekolah LIMIT 1", one=True)
        if row:
            sets = ", ".join(f"{f}=%s" for f in fields)
            execute(f"UPDATE sekolah SET {sets} WHERE id=%s", (*vals, row["id"]))
        else:
            cols = ", ".join(fields)
            ph = ", ".join(["%s"] * len(fields))
            execute(f"INSERT INTO sekolah ({cols}) VALUES ({ph})", vals)
        flash("Data sekolah disimpan.", "success")
        return redirect(url_for("main.data_sekolah"))
    sekolah = query("SELECT * FROM sekolah LIMIT 1", one=True) or {}
    return render_template("sekolah.html", sekolah=sekolah, nav="sekolah")


# ---------- Guru ----------
@bp.route("/admin/guru")
@login_required
def data_guru():
    from .guru_excel import ensure_guru_columns
    if not any(col["Field"] == "mapel_ajar" for col in query("SHOW COLUMNS FROM guru")):
        ensure_guru_columns()
    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        rows = query(
            """SELECT * FROM guru
               WHERE nama LIKE %s OR nip LIKE %s OR nuptk LIKE %s OR mapel_ajar LIKE %s
               ORDER BY nama""",
            (like, like, like, like),
        )
    else:
        rows = query("SELECT * FROM guru ORDER BY nama")
    return render_template("list_guru.html", rows=rows, q=q, nav="guru")


@bp.route("/admin/guru/upload", methods=["POST"])
@login_required
def upload_guru():
    berkas = request.files.get("berkas")
    if not berkas or not berkas.filename:
        flash("Pilih file Excel jadwal pelajaran terlebih dahulu.", "error")
        return redirect(url_for("main.data_guru"))
    try:
        records = parse_guru_file(berkas.filename, berkas.read())
        jumlah = replace_guru(records)
    except Exception as exc:
        flash(str(exc) or "File Excel tidak bisa dibaca.", "error")
        return redirect(url_for("main.data_guru"))
    flash(f"{jumlah} guru berhasil diunggah dan daftar guru diganti.", "success")
    return redirect(url_for("main.data_guru"))


@bp.route("/admin/guru/form", methods=["GET", "POST"])
@bp.route("/admin/guru/form/<int:item_id>", methods=["GET", "POST"])
@login_required
def form_guru(item_id=None):
    row = query("SELECT * FROM guru WHERE id=%s", (item_id,), one=True) if item_id else None
    if item_id and not row:
        return _missing(row, "main.data_guru")
    if request.method == "POST":
        tanggal = clean_date(request.form.get("tanggal_lahir"))
        if tanggal is False:
            flash("Tanggal lahir tidak valid.", "error")
            return redirect(request.url)
        data = (
            request.form.get("nip"),
            request.form.get("nuptk"),
            request.form.get("nama"),
            request.form.get("gelar_depan") or "",
            request.form.get("gelar_belakang") or "",
            request.form.get("jenis_kelamin") or "L",
            request.form.get("tempat_lahir"),
            tanggal,
            request.form.get("agama") or "Islam",
            request.form.get("alamat"),
            request.form.get("no_hp"),
            request.form.get("email"),
            request.form.get("status_kepegawaian") or "Guru Tetap",
            request.form.get("mapel_ajar"),
            to_int(request.form.get("jumlah_jam"), 0),
            request.form.get("mengajar_di"),
            to_int(request.form.get("aktif"), 1),
        )
        if item_id:
            execute(
                """UPDATE guru SET nip=%s,nuptk=%s,nama=%s,gelar_depan=%s,gelar_belakang=%s,
                jenis_kelamin=%s,tempat_lahir=%s,tanggal_lahir=%s,agama=%s,alamat=%s,no_hp=%s,
                email=%s,status_kepegawaian=%s,mapel_ajar=%s,jumlah_jam=%s,mengajar_di=%s,aktif=%s WHERE id=%s""",
                (*data, item_id),
            )
            flash("Data guru diperbarui.", "success")
        else:
            execute(
                """INSERT INTO guru (nip,nuptk,nama,gelar_depan,gelar_belakang,jenis_kelamin,
                tempat_lahir,tanggal_lahir,agama,alamat,no_hp,email,status_kepegawaian,
                mapel_ajar,jumlah_jam,mengajar_di,aktif)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                data,
            )
            flash("Guru baru ditambahkan.", "success")
        return redirect(url_for("main.data_guru"))
    return render_template("form_guru.html", row=row or {}, nav="guru")


@bp.route("/admin/guru/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_guru(item_id):
    blocked = _in_use(
        """SELECT (
             (SELECT COUNT(*) FROM pelajaran WHERE guru_id=%s) +
             (SELECT COUNT(*) FROM kelas WHERE wali_kelas_id=%s) +
             (SELECT COUNT(*) FROM ekstrakurikuler WHERE pembina_id=%s) +
             (SELECT COUNT(*) FROM mapping_guru_tahfiz WHERE guru_id=%s) +
             (SELECT COUNT(*) FROM users WHERE guru_id=%s)
           ) AS n""",
        (item_id, item_id, item_id, item_id, item_id),
        "Guru masih dipakai di kelas, pelajaran, ekskul, atau tahfiz. Lepaskan dulu sebelum menghapus.",
        "main.data_guru",
    )
    if blocked:
        return blocked
    execute("DELETE FROM guru WHERE id=%s", (item_id,))
    flash("Data guru dihapus.", "success")
    return redirect(url_for("main.data_guru"))


# ---------- Kelas ----------
@bp.route("/admin/kelas")
@login_required
def data_kelas():
    ta_id = _ta_id()
    rows = query(
        """SELECT k.*, g.nama AS wali
           FROM kelas k LEFT JOIN guru g ON g.id=k.wali_kelas_id
           WHERE k.tahun_ajaran_id=%s ORDER BY """ + ORDER_KELAS_K,
        (ta_id,),
    ) if ta_id else []
    return render_template("list_kelas.html", rows=rows, nav="kelas")


@bp.route("/admin/kelas/form", methods=["GET", "POST"])
@bp.route("/admin/kelas/form/<int:item_id>", methods=["GET", "POST"])
@login_required
def form_kelas(item_id=None):
    row = query("SELECT * FROM kelas WHERE id=%s", (item_id,), one=True) if item_id else None
    if item_id and not row:
        return _missing(row, "main.data_kelas")
    guru = query("SELECT id, nama FROM guru WHERE aktif=1 ORDER BY nama")
    if request.method == "POST":
        ta_id = _ta_id()
        if not ta_id:
            flash("Tahun ajaran aktif belum diatur.", "error")
            return redirect(url_for("main.data_kelas"))
        data = (
            request.form.get("nama"),
            request.form.get("tingkat"),
            request.form.get("jurusan") or "Umum",
            request.form.get("wali_kelas_id") or None,
            ta_id,
            to_int(request.form.get("kapasitas"), 36),
        )
        if item_id:
            execute(
                "UPDATE kelas SET nama=%s,tingkat=%s,jurusan=%s,wali_kelas_id=%s,tahun_ajaran_id=%s,kapasitas=%s WHERE id=%s",
                (*data, item_id),
            )
            flash("Data kelas diperbarui.", "success")
        else:
            execute(
                "INSERT INTO kelas (nama,tingkat,jurusan,wali_kelas_id,tahun_ajaran_id,kapasitas) VALUES (%s,%s,%s,%s,%s,%s)",
                data,
            )
            flash("Kelas baru ditambahkan.", "success")
        return redirect(url_for("main.data_kelas"))
    return render_template("form_kelas.html", row=row or {}, guru=guru, nav="kelas")


@bp.route("/admin/kelas/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_kelas(item_id):
    blocked = _in_use(
        """SELECT (
             (SELECT COUNT(*) FROM siswa WHERE kelas_id=%s) +
             (SELECT COUNT(*) FROM pelajaran WHERE kelas_id=%s)
           ) AS n""",
        (item_id, item_id),
        "Kelas masih memiliki siswa atau pembelajaran. Kosongkan dulu sebelum menghapus.",
        "main.data_kelas",
    )
    if blocked:
        return blocked
    execute("DELETE FROM kelas WHERE id=%s", (item_id,))
    flash("Kelas dihapus.", "success")
    return redirect(url_for("main.data_kelas"))


# ---------- Siswa ----------
@bp.route("/admin/siswa")
@login_required
def data_siswa():
    q = (request.args.get("q") or "").strip()
    kelas_id = request.args.get("kelas_id") or ""
    kelas = query(f"SELECT id, nama FROM kelas ORDER BY {ORDER_KELAS}")
    sql = """SELECT s.*, k.nama AS kelas_nama FROM siswa s
             LEFT JOIN kelas k ON k.id=s.kelas_id WHERE 1=1"""
    params = []
    if q:
        sql += " AND (s.nama LIKE %s OR s.nis LIKE %s OR s.nisn LIKE %s)"
        like = f"%{q}%"
        params.extend([like, like, like])
    if "admin" not in set(session.get("tugas") or []) and session.get("role") != "admin":
        sql += " AND s.kelas_id IN (SELECT id FROM kelas WHERE wali_kelas_id=%s)"
        params.append(session.get("guru_id") or 0)
    if kelas_id:
        sql += " AND s.kelas_id=%s"
        params.append(kelas_id)
    sql += f" ORDER BY {ORDER_KELAS_K}, s.nama"
    rows = query(sql, params)
    return render_template("list_siswa.html", rows=rows, kelas=kelas, q=q, kelas_id=kelas_id, nav="siswa")


@bp.route("/admin/siswa/form", methods=["GET", "POST"])
@bp.route("/admin/siswa/form/<int:item_id>", methods=["GET", "POST"])
@login_required
def form_siswa(item_id=None):
    row = query("SELECT * FROM siswa WHERE id=%s", (item_id,), one=True) if item_id else None
    if item_id and not row:
        return _missing(row, "main.data_siswa")
    kelas = query(f"SELECT id, nama FROM kelas ORDER BY {ORDER_KELAS}")
    if request.method == "POST":
        tanggal = clean_date(request.form.get("tanggal_lahir"))
        if tanggal is False:
            flash("Tanggal lahir tidak valid.", "error")
            return redirect(request.url)
        data = (
            request.form.get("nis"),
            request.form.get("nisn"),
            request.form.get("nama"),
            request.form.get("jenis_kelamin") or "L",
            request.form.get("tempat_lahir"),
            tanggal,
            request.form.get("agama") or "Islam",
            request.form.get("alamat"),
            request.form.get("nama_ayah"),
            request.form.get("nama_ibu"),
            request.form.get("no_hp"),
            request.form.get("kelas_id") or None,
            request.form.get("status") or "aktif",
        )
        if item_id:
            execute(
                """UPDATE siswa SET nis=%s,nisn=%s,nama=%s,jenis_kelamin=%s,tempat_lahir=%s,
                tanggal_lahir=%s,agama=%s,alamat=%s,nama_ayah=%s,nama_ibu=%s,no_hp=%s,
                kelas_id=%s,status=%s WHERE id=%s""",
                (*data, item_id),
            )
            flash("Data siswa diperbarui.", "success")
        else:
            execute(
                """INSERT INTO siswa (nis,nisn,nama,jenis_kelamin,tempat_lahir,tanggal_lahir,
                agama,alamat,nama_ayah,nama_ibu,no_hp,kelas_id,status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                data,
            )
            flash("Siswa baru ditambahkan.", "success")
        return redirect(url_for("main.data_siswa"))
    return render_template("form_siswa.html", row=row or {}, kelas=kelas, nav="siswa")


@bp.route("/admin/siswa/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_siswa(item_id):
    execute("DELETE FROM siswa WHERE id=%s", (item_id,))
    flash("Data siswa dihapus.", "success")
    return redirect(url_for("main.data_siswa"))


# ---------- Kelompok mapel ----------
@bp.route("/admin/kelompok-mapel", methods=["GET", "POST"])
@login_required
def data_kelompok():
    if request.method == "POST":
        execute(
            "INSERT INTO kelompok_mapel (kode,nama,urutan) VALUES (%s,%s,%s)",
            (request.form.get("kode"), request.form.get("nama"), to_int(request.form.get("urutan"), 0)),
        )
        flash("Kelompok mapel ditambahkan.", "success")
        return redirect(url_for("main.data_kelompok"))
    rows = query("SELECT * FROM kelompok_mapel ORDER BY urutan, id")
    return render_template("list_kelompok.html", rows=rows, nav="kelompok")


@bp.route("/admin/kelompok-mapel/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_kelompok(item_id):
    blocked = _in_use(
        "SELECT COUNT(*) AS n FROM mata_pelajaran WHERE kelompok_id=%s",
        (item_id,),
        "Kelompok masih dipakai mata pelajaran. Pindahkan mapelnya dulu.",
        "main.data_kelompok",
    )
    if blocked:
        return blocked
    execute("DELETE FROM kelompok_mapel WHERE id=%s", (item_id,))
    flash("Kelompok mapel dihapus.", "success")
    return redirect(url_for("main.data_kelompok"))


# ---------- Mapel ----------
@bp.route("/admin/mapel")
@login_required
def data_mapel():
    rows = query(
        """SELECT m.*, k.nama AS kelompok FROM mata_pelajaran m
           LEFT JOIN kelompok_mapel k ON k.id=m.kelompok_id ORDER BY k.urutan, m.nama"""
    )
    return render_template("list_mapel.html", rows=rows, nav="mapel")


@bp.route("/admin/mapel/form", methods=["GET", "POST"])
@bp.route("/admin/mapel/form/<int:item_id>", methods=["GET", "POST"])
@login_required
def form_mapel(item_id=None):
    row = query("SELECT * FROM mata_pelajaran WHERE id=%s", (item_id,), one=True) if item_id else None
    if item_id and not row:
        return _missing(row, "main.data_mapel")
    kelompok = query("SELECT * FROM kelompok_mapel ORDER BY urutan")
    if request.method == "POST":
        data = (
            request.form.get("kode"),
            request.form.get("nama"),
            request.form.get("kelompok_id") or None,
            to_int(request.form.get("kkm_default"), 75),
        )
        if item_id:
            execute("UPDATE mata_pelajaran SET kode=%s,nama=%s,kelompok_id=%s,kkm_default=%s WHERE id=%s", (*data, item_id))
            flash("Mata pelajaran diperbarui.", "success")
        else:
            execute("INSERT INTO mata_pelajaran (kode,nama,kelompok_id,kkm_default) VALUES (%s,%s,%s,%s)", data)
            flash("Mata pelajaran ditambahkan.", "success")
        return redirect(url_for("main.data_mapel"))
    return render_template("form_mapel.html", row=row or {}, kelompok=kelompok, nav="mapel")


@bp.route("/admin/mapel/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_mapel(item_id):
    blocked = _in_use(
        "SELECT COUNT(*) AS n FROM pelajaran WHERE mapel_id=%s",
        (item_id,),
        "Mata pelajaran masih dipakai di data pelajaran. Lepaskan dulu sebelum menghapus.",
        "main.data_mapel",
    )
    if blocked:
        return blocked
    execute("DELETE FROM mata_pelajaran WHERE id=%s", (item_id,))
    flash("Mata pelajaran dihapus.", "success")
    return redirect(url_for("main.data_mapel"))


# ---------- Pelajaran / pembelajaran ----------
@bp.route("/admin/pelajaran")
@login_required
def data_pelajaran():
    ta_id = _ta_id()
    extra = ""
    params = [ta_id]
    if "admin" not in set(session.get("tugas") or []) and session.get("role") != "admin":
        extra = " AND p.guru_id=%s"
        params.append(session.get("guru_id") or 0)
    rows = query(
        """SELECT p.*, k.nama AS kelas_nama, m.nama AS mapel_nama, g.nama AS guru_nama
           FROM pelajaran p
           JOIN kelas k ON k.id=p.kelas_id
           JOIN mata_pelajaran m ON m.id=p.mapel_id
           JOIN guru g ON g.id=p.guru_id
           WHERE p.tahun_ajaran_id=%s
           """ + extra + " ORDER BY " + ORDER_KELAS_K + ", m.nama",
        params,
    ) if ta_id else []
    return render_template("list_pelajaran.html", rows=rows, nav="pelajaran")


@bp.route("/admin/pelajaran/form", methods=["GET", "POST"])
@bp.route("/admin/pelajaran/form/<int:item_id>", methods=["GET", "POST"])
@login_required
def form_pelajaran(item_id=None):
    row = query("SELECT * FROM pelajaran WHERE id=%s", (item_id,), one=True) if item_id else None
    if item_id and not row:
        return _missing(row, "main.data_pelajaran")
    kelas = query(f"SELECT id, nama FROM kelas ORDER BY {ORDER_KELAS}")
    mapel = query("SELECT id, nama FROM mata_pelajaran ORDER BY nama")
    guru = query("SELECT id, nama FROM guru WHERE aktif=1 ORDER BY nama")
    if request.method == "POST":
        ta_id = _ta_id()
        if not ta_id:
            flash("Tahun ajaran aktif belum diatur.", "error")
            return redirect(url_for("main.data_pelajaran"))
        data = (
            ta_id,
            request.form.get("kelas_id"),
            request.form.get("mapel_id"),
            request.form.get("guru_id"),
            to_int(request.form.get("jam_per_minggu"), 2),
        )
        try:
            if item_id:
                execute(
                    "UPDATE pelajaran SET tahun_ajaran_id=%s,kelas_id=%s,mapel_id=%s,guru_id=%s,jam_per_minggu=%s WHERE id=%s",
                    (*data, item_id),
                )
                flash("Pembelajaran diperbarui.", "success")
            else:
                execute(
                    "INSERT INTO pelajaran (tahun_ajaran_id,kelas_id,mapel_id,guru_id,jam_per_minggu) VALUES (%s,%s,%s,%s,%s)",
                    data,
                )
                flash("Pembelajaran ditambahkan.", "success")
        except Exception:
            flash("Gagal menyimpan. Mapel itu sudah terdaftar di kelas yang sama, atau data tidak valid.", "error")
        return redirect(url_for("main.data_pelajaran"))
    return render_template(
        "form_pelajaran.html", row=row or {}, kelas=kelas, mapel=mapel, guru=guru, nav="pelajaran"
    )


@bp.route("/admin/pelajaran/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_pelajaran(item_id):
    execute("DELETE FROM pelajaran WHERE id=%s", (item_id,))
    flash("Pembelajaran dihapus.", "success")
    return redirect(url_for("main.data_pelajaran"))


# ---------- Gabung mapel ----------
@bp.route("/admin/gabung-mapel", methods=["GET", "POST"])
@login_required
def gabung_mapel():
    if request.method == "POST":
        ids = request.form.getlist("mapel_id")
        with transaction():
            gid = execute("INSERT INTO gabung_mapel (nama_gabungan) VALUES (%s)", (request.form.get("nama_gabungan"),))
            for mid in ids:
                execute("INSERT INTO gabung_mapel_item (gabung_id, mapel_id) VALUES (%s,%s)", (gid, mid))
        flash("Gabungan mapel disimpan.", "success")
        return redirect(url_for("main.gabung_mapel"))
    rows = query("SELECT * FROM gabung_mapel ORDER BY id")
    for r in rows:
        items = query(
            """SELECT m.nama FROM gabung_mapel_item i JOIN mata_pelajaran m ON m.id=i.mapel_id WHERE i.gabung_id=%s""",
            (r["id"],),
        )
        r["items"] = ", ".join(x["nama"] for x in items)
    mapel = query("SELECT id, nama FROM mata_pelajaran ORDER BY nama")
    return render_template("list_gabung.html", rows=rows, mapel=mapel, nav="gabung")


@bp.route("/admin/gabung-mapel/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_gabung(item_id):
    execute("DELETE FROM gabung_mapel WHERE id=%s", (item_id,))
    flash("Gabungan mapel dihapus.", "success")
    return redirect(url_for("main.gabung_mapel"))


# ---------- Mapping rapor ----------
@bp.route("/admin/mapping-rapor", methods=["GET", "POST"])
@login_required
def mapping_rapor():
    if request.method == "POST":
        chosen = request.form.getlist("mapel_id")
        with transaction():
            execute("DELETE FROM mapping_rapor")
            for mid in chosen:
                urutan = to_int(request.form.get(f"urutan_{mid}"), 0)
                execute("INSERT INTO mapping_rapor (mapel_id, tampil_rapor, urutan) VALUES (%s,1,%s)", (mid, urutan))
        flash("Mapping rapor disimpan.", "success")
        return redirect(url_for("main.mapping_rapor"))
    mapel = query("SELECT * FROM mata_pelajaran ORDER BY nama")
    mapped = {r["mapel_id"]: r for r in query("SELECT * FROM mapping_rapor")}
    return render_template("mapping_rapor.html", mapel=mapel, mapped=mapped, nav="mapping")


# ---------- Ekskul ----------
@bp.route("/admin/ekskul", methods=["GET", "POST"])
@login_required
def data_ekskul():
    if request.method == "POST":
        if "admin" not in set(session.get("tugas") or []) and session.get("role") != "admin":
            flash("Hanya admin yang dapat menambah ekstrakurikuler.", "error")
            return redirect(url_for("main.data_ekskul"))
        execute(
            "INSERT INTO ekstrakurikuler (nama, pembina_id) VALUES (%s,%s)",
            (request.form.get("nama"), request.form.get("pembina_id") or None),
        )
        flash("Ekstrakurikuler ditambahkan.", "success")
        return redirect(url_for("main.data_ekskul"))
    if "admin" not in set(session.get("tugas") or []) and session.get("role") != "admin":
        rows = query(
            """SELECT e.*, g.nama AS pembina FROM ekstrakurikuler e
               LEFT JOIN guru g ON g.id=e.pembina_id
               WHERE e.pembina_id=%s ORDER BY e.nama""",
            (session.get("guru_id") or 0,),
        )
    else:
        rows = query(
            """SELECT e.*, g.nama AS pembina FROM ekstrakurikuler e
               LEFT JOIN guru g ON g.id=e.pembina_id ORDER BY e.nama"""
        )
    guru = query("SELECT id, nama FROM guru WHERE aktif=1 ORDER BY nama")
    return render_template("list_ekskul.html", rows=rows, guru=guru, nav="ekskul")


@bp.route("/admin/ekskul/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_ekskul(item_id):
    execute("DELETE FROM ekstrakurikuler WHERE id=%s", (item_id,))
    flash("Ekstrakurikuler dihapus.", "success")
    return redirect(url_for("main.data_ekskul"))


# ---------- Tryout ----------
@bp.route("/admin/tryout", methods=["GET", "POST"])
@login_required
def data_tryout():
    if request.method == "POST":
        execute(
            "INSERT INTO tryout (nama, tanggal, tingkat) VALUES (%s,%s,%s)",
            (request.form.get("nama"), request.form.get("tanggal") or None, request.form.get("tingkat") or "XII"),
        )
        flash("Tryout ditambahkan.", "success")
        return redirect(url_for("main.data_tryout"))
    rows = query("SELECT * FROM tryout ORDER BY tanggal DESC")
    return render_template("list_tryout.html", rows=rows, nav="tryout")


@bp.route("/admin/tryout/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_tryout(item_id):
    execute("DELETE FROM tryout WHERE id=%s", (item_id,))
    flash("Tryout dihapus.", "success")
    return redirect(url_for("main.data_tryout"))


# ---------- Perencanaan penilaian ----------
@bp.route("/admin/perencanaan")
@login_required
def perencanaan():
    ta_id = _ta_id()
    extra = ""
    params = [ta_id]
    if "admin" not in set(session.get("tugas") or []) and session.get("role") != "admin":
        extra = " AND pel.guru_id=%s"
        params.append(session.get("guru_id") or 0)
    rows = query(
        """SELECT pel.id, k.nama AS kelas_nama, m.nama AS mapel_nama, g.nama AS guru_nama,
                  r.id AS rencana_id, r.jumlah_tp, r.kkm, r.mapped
           FROM pelajaran pel
           JOIN kelas k ON k.id=pel.kelas_id
           JOIN mata_pelajaran m ON m.id=pel.mapel_id
           JOIN guru g ON g.id=pel.guru_id
           LEFT JOIN perencanaan_penilaian r ON r.pelajaran_id=pel.id
           WHERE pel.tahun_ajaran_id=%s
           """ + extra + " ORDER BY k.nama, m.nama",
        params,
    ) if ta_id else []
    return render_template("perencanaan.html", rows=rows, nav="perencanaan")


@bp.route("/admin/perencanaan/simpan/<int:pelajaran_id>", methods=["POST"])
@login_required
def simpan_perencanaan(pelajaran_id):
    if "admin" not in set(session.get("tugas") or []) and session.get("role") != "admin":
        milik = query(
            "SELECT id FROM pelajaran WHERE id=%s AND guru_id=%s",
            (pelajaran_id, session.get("guru_id") or 0),
            one=True,
        )
        if not milik:
            flash("Perencanaan ini bukan tugas Anda.", "error")
            return redirect(url_for("main.perencanaan"))
    jumlah = to_int(request.form.get("jumlah_tp"), 4)
    kkm = to_int(request.form.get("kkm"), 75)
    mapped = 1 if request.form.get("mapped") else 0
    existing = query("SELECT id FROM perencanaan_penilaian WHERE pelajaran_id=%s", (pelajaran_id,), one=True)
    if existing:
        execute(
            "UPDATE perencanaan_penilaian SET jumlah_tp=%s,kkm=%s,mapped=%s WHERE pelajaran_id=%s",
            (jumlah, kkm, mapped, pelajaran_id),
        )
    else:
        execute(
            "INSERT INTO perencanaan_penilaian (pelajaran_id,jumlah_tp,kkm,mapped) VALUES (%s,%s,%s,%s)",
            (pelajaran_id, jumlah, kkm, mapped),
        )
    flash("Perencanaan penilaian disimpan.", "success")
    return redirect(url_for("main.perencanaan"))


# ---------- Tahfiz ----------
@bp.route("/admin/tahfiz/aspek", methods=["GET", "POST"])
@login_required
def aspek_tahfiz():
    if request.method == "POST":
        execute(
            "INSERT INTO aspek_tahfiz (nama, jenis, kkm) VALUES (%s,%s,%s)",
            (request.form.get("nama"), request.form.get("jenis") or "Hafalan", to_int(request.form.get("kkm"), 75)),
        )
        flash("Aspek tahfiz ditambahkan.", "success")
        return redirect(url_for("main.aspek_tahfiz"))
    rows = query("SELECT * FROM aspek_tahfiz ORDER BY id")
    return render_template("list_aspek.html", rows=rows, nav="aspek")


@bp.route("/admin/tahfiz/aspek/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_aspek(item_id):
    blocked = _in_use(
        """SELECT (
             (SELECT COUNT(*) FROM mapping_guru_tahfiz WHERE aspek_id=%s) +
             (SELECT COUNT(*) FROM nilai_tahfiz WHERE aspek_id=%s)
           ) AS n""",
        (item_id, item_id),
        "Aspek masih dipakai di mapping guru atau nilai tahfiz.",
        "main.aspek_tahfiz",
    )
    if blocked:
        return blocked
    execute("DELETE FROM aspek_tahfiz WHERE id=%s", (item_id,))
    flash("Aspek dihapus.", "success")
    return redirect(url_for("main.aspek_tahfiz"))


@bp.route("/admin/tahfiz/mapping", methods=["GET", "POST"])
@login_required
def mapping_tahfiz():
    if request.method == "POST":
        execute(
            "INSERT INTO mapping_guru_tahfiz (guru_id,kelas_id,aspek_id) VALUES (%s,%s,%s)",
            (request.form.get("guru_id"), request.form.get("kelas_id"), request.form.get("aspek_id")),
        )
        flash("Mapping guru tahfiz disimpan.", "success")
        return redirect(url_for("main.mapping_tahfiz"))
    rows = query(
        """SELECT m.id, g.nama AS guru_nama, k.nama AS kelas_nama, a.nama AS aspek_nama
           FROM mapping_guru_tahfiz m
           JOIN guru g ON g.id=m.guru_id
           JOIN kelas k ON k.id=m.kelas_id
           JOIN aspek_tahfiz a ON a.id=m.aspek_id
           ORDER BY k.nama"""
    )
    return render_template(
        "mapping_tahfiz.html",
        rows=rows,
        guru=query("SELECT id,nama FROM guru WHERE aktif=1 ORDER BY nama"),
        kelas=query(f"SELECT id,nama FROM kelas ORDER BY {ORDER_KELAS}"),
        aspek=query("SELECT id,nama FROM aspek_tahfiz"),
        nav="maptahfiz",
    )


@bp.route("/admin/tahfiz/mapping/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_mapping_tahfiz(item_id):
    execute("DELETE FROM mapping_guru_tahfiz WHERE id=%s", (item_id,))
    flash("Mapping dihapus.", "success")
    return redirect(url_for("main.mapping_tahfiz"))


@bp.route("/admin/tahfiz/pengaturan", methods=["GET", "POST"])
@login_required
def pengaturan_tahfiz():
    if request.method == "POST":
        row = query("SELECT id FROM pengaturan_rapor_tahfiz LIMIT 1", one=True)
        data = (
            1 if request.form.get("tampilkan") else 0,
            request.form.get("judul") or "Rapor Tahfiz",
            request.form.get("keterangan"),
        )
        if row:
            execute("UPDATE pengaturan_rapor_tahfiz SET tampilkan=%s,judul=%s,keterangan=%s WHERE id=%s", (*data, row["id"]))
        else:
            execute("INSERT INTO pengaturan_rapor_tahfiz (tampilkan,judul,keterangan) VALUES (%s,%s,%s)", data)
        flash("Pengaturan rapor tahfiz disimpan.", "success")
        return redirect(url_for("main.pengaturan_tahfiz"))
    row = query("SELECT * FROM pengaturan_rapor_tahfiz LIMIT 1", one=True) or {}
    return render_template("pengaturan_tahfiz.html", row=row, nav="pengtahfiz")


@bp.route("/admin/tahfiz/nilai")
@login_required
def nilai_tahfiz():
    kelas_id = request.args.get("kelas_id") or ""
    aspek_id = request.args.get("aspek_id") or ""
    siswa = []
    if kelas_id and aspek_id:
        ta_id = _ta_id()
        siswa = query(
            """SELECT s.id, s.nis, s.nama, n.nilai, n.predikat, n.deskripsi
               FROM siswa s
               LEFT JOIN nilai_tahfiz n ON n.siswa_id=s.id AND n.aspek_id=%s AND n.tahun_ajaran_id=%s
               WHERE s.kelas_id=%s AND s.status='aktif' ORDER BY s.nama""",
            (aspek_id, ta_id, kelas_id),
        )
    if "admin" in set(session.get("tugas") or []) or session.get("role") == "admin":
        kelas_opsi = query(f"SELECT id,nama FROM kelas ORDER BY {ORDER_KELAS}")
    else:
        kelas_opsi = query(
            f"""SELECT DISTINCT k.id, k.nama FROM kelas k
                JOIN mapping_guru_tahfiz m ON m.kelas_id=k.id
                WHERE m.guru_id=%s ORDER BY {ORDER_KELAS_K}""",
            (session.get("guru_id") or 0,),
        )
    return render_template(
        "nilai_tahfiz.html",
        siswa=siswa,
        kelas=kelas_opsi,
        aspek=query("SELECT id,nama FROM aspek_tahfiz"),
        kelas_id=kelas_id,
        aspek_id=aspek_id,
        nav="nilaitahfiz",
    )


@bp.route("/admin/tahfiz/nilai/simpan", methods=["POST"])
@login_required
def simpan_nilai_tahfiz():
    ta_id = _ta_id()
    aspek_id = request.form.get("aspek_id")
    kelas_id = request.form.get("kelas_id")
    if not ta_id or not aspek_id:
        flash("Pilih kelas, aspek, dan pastikan tahun ajaran aktif.", "error")
        return redirect(url_for("main.nilai_tahfiz", kelas_id=kelas_id, aspek_id=aspek_id))
    ids = request.form.getlist("siswa_id")
    with transaction():
        for sid in ids:
            raw = request.form.get(f"nilai_{sid}")
            predikat = request.form.get(f"predikat_{sid}") or None
            deskripsi = request.form.get(f"deskripsi_{sid}") or None
            if raw in (None, ""):
                continue
            nilai = clean_nilai(raw)
            if nilai is None:
                raise InputError("nilai")
            execute(
                """INSERT INTO nilai_tahfiz (siswa_id,aspek_id,tahun_ajaran_id,nilai,predikat,deskripsi)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE nilai=VALUES(nilai), predikat=VALUES(predikat), deskripsi=VALUES(deskripsi)""",
                (sid, aspek_id, ta_id, nilai, predikat, deskripsi),
            )
    flash("Nilai tahfiz disimpan.", "success")
    return redirect(url_for("main.nilai_tahfiz", kelas_id=kelas_id, aspek_id=aspek_id))
