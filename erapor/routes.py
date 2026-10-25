from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from flask import Blueprint, flash, redirect, render_template, request, send_file, session, url_for
from .auth import login_required
from .db import execute, query, transaction
from .guru_excel import formulir_guru, parse_guru_file, replace_guru

class InputError(ValueError):
    pass


bp = Blueprint("main", __name__)

TINGKAT_KELAS = ("7", "8", "9")
KURIKULUM_SEKOLAH = ("Kurikulum Merdeka", "Kurikulum 2013")
ORDER_KELAS = (
    "FIELD(tingkat,'7','8','9'), "
    "CAST(SUBSTRING_INDEX(nama,'-',-1) AS UNSIGNED), nama"
)
ORDER_KELAS_K = (
    "FIELD(k.tingkat,'7','8','9'), "
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
def _halaman_sekolah():
    per = request.args.get("per", 10, type=int) or 10
    if per not in (10, 25, 50, 100):
        per = 10
    halaman = request.args.get("halaman", 1, type=int) or 1
    if halaman < 1:
        halaman = 1
    return per, halaman


def _isi_sekolah():
    def kosong(nama):
        return (request.form.get(nama) or "").strip() or None

    tanggal = clean_date(request.form.get("tanggal_rapor"))
    if tanggal is False:
        flash("Tanggal pembagian rapor tidak valid.", "error")
        return None
    if not tanggal:
        flash("Tanggal pembagian rapor wajib diisi.", "error")
        return None
    nama = (request.form.get("nama") or "").strip()
    npsn = (request.form.get("npsn") or "").strip()
    if not nama or not npsn:
        flash("Nama sekolah dan NPSN wajib diisi.", "error")
        return None
    return (
        nama,
        npsn,
        kosong("status_sekolah"),
        kosong("alamat"),
        kosong("kelurahan"),
        kosong("kecamatan"),
        kosong("kabupaten"),
        kosong("provinsi"),
        kosong("kode_pos"),
        kosong("telepon"),
        kosong("email"),
        kosong("tempat_rapor"),
        tanggal,
        kosong("kepala_sekolah"),
        kosong("nip_kepala"),
    )


@bp.route("/admin/sekolah")
@login_required
def data_sekolah():
    q = (request.args.get("q") or "").strip()
    per, halaman = _halaman_sekolah()
    where = ""
    params = []
    if q:
        where = "WHERE nama LIKE %s OR npsn LIKE %s OR alamat LIKE %s OR kabupaten LIKE %s OR kepala_sekolah LIKE %s"
        like = f"%{q}%"
        params = [like, like, like, like, like]
    total = query(f"SELECT COUNT(*) AS n FROM sekolah {where}", params, one=True)["n"]
    halaman_max = max((total + per - 1) // per, 1)
    if halaman > halaman_max:
        halaman = halaman_max
    awal = 0 if total == 0 else (halaman - 1) * per + 1
    rows = query(
        f"""SELECT id, nama, npsn, alamat, kabupaten, kepala_sekolah
            FROM sekolah {where}
            ORDER BY nama, id
            LIMIT %s OFFSET %s""",
        (*params, per, (halaman - 1) * per),
    )
    akhir = 0 if total == 0 else awal + len(rows) - 1
    return render_template(
        "sekolah.html",
        rows=rows,
        q=q,
        per=per,
        halaman=halaman,
        total=total,
        awal=awal,
        akhir=akhir,
        nav="sekolah",
    )


@bp.route("/admin/sekolah/form", methods=["GET", "POST"])
@bp.route("/admin/sekolah/form/<int:item_id>", methods=["GET", "POST"])
@login_required
def form_sekolah(item_id=None):
    row = query("SELECT * FROM sekolah WHERE id=%s", (item_id,), one=True) if item_id else None
    if item_id and not row:
        flash("Data sekolah tidak ditemukan.", "error")
        return redirect(url_for("main.data_sekolah"))
    if request.method == "POST":
        data = _isi_sekolah()
        if data is None:
            return redirect(request.url)
        if row:
            execute(
                """UPDATE sekolah
                   SET nama=%s, npsn=%s, status_sekolah=%s, alamat=%s, kelurahan=%s, kecamatan=%s,
                       kabupaten=%s, provinsi=%s, kode_pos=%s, telepon=%s, email=%s,
                       tempat_rapor=%s, tanggal_rapor=%s, kepala_sekolah=%s, nip_kepala=%s
                   WHERE id=%s""",
                (*data, row["id"]),
            )
            flash("Data sekolah disimpan.", "success")
        else:
            execute(
                """INSERT INTO sekolah
                   (nama, npsn, status_sekolah, alamat, kelurahan, kecamatan, kabupaten, provinsi,
                    kode_pos, telepon, email, tempat_rapor, tanggal_rapor, kepala_sekolah, nip_kepala, jenjang)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'SMP')""",
                data,
            )
            flash("Sekolah baru disimpan.", "success")
        return redirect(url_for("main.data_sekolah"))
    return render_template("sekolah_form.html", row=row or {}, nav="sekolah")


@bp.route("/admin/sekolah/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_sekolah(item_id):
    execute("DELETE FROM sekolah WHERE id=%s", (item_id,))
    flash("Data sekolah dihapus.", "success")
    return redirect(url_for("main.data_sekolah"))


# ---------- Guru ----------
@bp.route("/admin/guru")
@login_required
def data_guru():
    from .guru_excel import ensure_guru_columns
    ensure_guru_columns()
    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        rows = query(
            """SELECT * FROM guru
               WHERE nama LIKE %s OR nip LIKE %s OR nbm LIKE %s OR nuptk LIKE %s OR mapel_ajar LIKE %s
               ORDER BY nama""",
            (like, like, like, like, like),
        )
    else:
        rows = query("SELECT * FROM guru ORDER BY nama")
    return render_template("list_guru.html", rows=rows, q=q, nav="guru")


@bp.route("/admin/guru/form-excel")
@login_required
def form_excel_guru():
    return send_file(
        formulir_guru(),
        as_attachment=True,
        download_name="Form Data Guru.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


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
    from .guru_excel import ensure_guru_columns
    ensure_guru_columns()
    row = query("SELECT * FROM guru WHERE id=%s", (item_id,), one=True) if item_id else None
    if item_id and not row:
        return _missing(row, "main.data_guru")
    if request.method == "POST":
        tanggal = clean_date(request.form.get("tanggal_lahir"))
        if tanggal is False:
            flash("Tanggal lahir tidak valid.", "error")
            return redirect(request.url)
        def kosong(nama):
            nilai = (request.form.get(nama) or "").strip()
            return nilai or None

        jk = request.form.get("jenis_kelamin") or ""
        if jk not in {"L", "P"}:
            jk = None
        jam = kosong("jumlah_jam")
        data = (
            kosong("nip"),
            kosong("nbm"),
            kosong("nuptk"),
            (request.form.get("nama") or "").strip(),
            (request.form.get("gelar_depan") or "").strip(),
            (request.form.get("gelar_belakang") or "").strip(),
            jk,
            kosong("tempat_lahir"),
            tanggal,
            request.form.get("agama") or "Islam",
            kosong("alamat"),
            kosong("no_hp"),
            kosong("email"),
            request.form.get("status_kepegawaian") or "Guru Tetap",
            kosong("mapel_ajar"),
            int(jam) if jam and jam.isdigit() else None,
            kosong("mengajar_di"),
            1 if request.form.get("aktif") != "0" else 0,
        )
        if item_id:
            execute(
                """UPDATE guru SET nip=%s,nbm=%s,nuptk=%s,nama=%s,gelar_depan=%s,gelar_belakang=%s,
                jenis_kelamin=%s,tempat_lahir=%s,tanggal_lahir=%s,agama=%s,alamat=%s,no_hp=%s,
                email=%s,status_kepegawaian=%s,mapel_ajar=%s,jumlah_jam=%s,mengajar_di=%s,aktif=%s WHERE id=%s""",
                (*data, item_id),
            )
            flash("Data guru diperbarui.", "success")
        else:
            execute(
                """INSERT INTO guru (nip,nbm,nuptk,nama,gelar_depan,gelar_belakang,jenis_kelamin,
                tempat_lahir,tanggal_lahir,agama,alamat,no_hp,email,status_kepegawaian,
                mapel_ajar,jumlah_jam,mengajar_di,aktif)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
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
        tingkat = request.form.get("tingkat")
        if tingkat not in TINGKAT_KELAS:
            flash("Tingkat kelas hanya 7, 8, atau 9.", "error")
            return redirect(request.url)
        data = (
            request.form.get("nama"),
            tingkat,
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
def _admin_sekolah():
    return session.get("role") == "admin" or "admin" in set(session.get("tugas") or [])


def _kelas_siswa():
    if _admin_sekolah():
        return query(f"SELECT id, nama FROM kelas ORDER BY {ORDER_KELAS}")
    return query(
        f"SELECT id, nama FROM kelas WHERE wali_kelas_id=%s ORDER BY {ORDER_KELAS}",
        (session.get("guru_id") or 0,),
    )


def _saringan_siswa():
    q = (request.args.get("q") or "").strip()
    kelas_id = request.args.get("kelas_id") or ""
    jk = request.args.get("jk") or ""
    if jk not in {"L", "P"}:
        jk = ""
    where = ["1=1"]
    params = []
    if q:
        where.append("(s.nama LIKE %s OR s.nis LIKE %s OR s.nisn LIKE %s OR s.nik LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like, like])
    if not _admin_sekolah():
        where.append("s.kelas_id IN (SELECT id FROM kelas WHERE wali_kelas_id=%s)")
        params.append(session.get("guru_id") or 0)
    if kelas_id.isdigit():
        where.append("s.kelas_id=%s")
        params.append(int(kelas_id))
    else:
        kelas_id = ""
    if jk:
        where.append("s.jenis_kelamin=%s")
        params.append(jk)
    return q, kelas_id, jk, " AND ".join(where), params


@bp.route("/admin/siswa")
@login_required
def data_siswa():
    q, kelas_id, jk, where, params = _saringan_siswa()
    per = request.args.get("per", 10, type=int) or 10
    if per not in (10, 25, 50, 100):
        per = 10
    halaman = request.args.get("halaman", 1, type=int) or 1
    if halaman < 1:
        halaman = 1
    urut = request.args.get("urut") or "nama"
    arah = "DESC" if request.args.get("arah") == "desc" else "ASC"
    if urut == "kelas":
        order = f"{ORDER_KELAS_K} {arah}, s.nama"
    elif urut == "nisn":
        order = f"s.nisn {arah}, s.nama"
    elif urut == "nis":
        order = f"s.nis {arah}, s.nama"
    else:
        urut = "nama"
        order = f"s.nama {arah}, s.nis"
    total = query(
        f"SELECT COUNT(*) AS n FROM siswa s LEFT JOIN kelas k ON k.id=s.kelas_id WHERE {where}",
        params,
        one=True,
    )["n"]
    halaman_max = max((total + per - 1) // per, 1)
    if halaman > halaman_max:
        halaman = halaman_max
    awal = 0 if total == 0 else (halaman - 1) * per + 1
    rows = query(
        f"""SELECT s.id, s.nama, s.nisn, s.nis, s.jenis_kelamin, k.nama AS kelas_nama
            FROM siswa s LEFT JOIN kelas k ON k.id=s.kelas_id
            WHERE {where} ORDER BY {order} LIMIT %s OFFSET %s""",
        (*params, per, (halaman - 1) * per),
    )
    akhir = 0 if total == 0 else awal + len(rows) - 1
    saring = int(bool(kelas_id)) + int(bool(jk))
    return render_template(
        "list_siswa.html",
        rows=rows,
        kelas=_kelas_siswa(),
        q=q,
        kelas_id=kelas_id,
        jk=jk,
        per=per,
        halaman=halaman,
        total=total,
        awal=awal,
        akhir=akhir,
        urut=urut,
        arah=arah.lower(),
        saring=saring,
        nav="siswa",
    )


def _isi_siswa():
    def kosong(nama):
        return (request.form.get(nama) or "").strip() or None

    tanggal = clean_date(request.form.get("tanggal_lahir"))
    if tanggal is False:
        flash("Tanggal lahir tidak valid.", "error")
        return None
    nama = (request.form.get("nama") or "").strip()
    nis = (request.form.get("nis") or "").strip()
    jk = request.form.get("jenis_kelamin") or ""
    kelas_id = request.form.get("kelas_id") or ""
    if not nama or not nis or not kelas_id.isdigit() or jk not in {"L", "P"}:
        flash("Nama, NIS, jenis kelamin, dan kelas wajib diisi.", "error")
        return None
    nik = kosong("nik")
    if nik and (len(nik) != 16 or not nik.isdigit()):
        flash("NIK harus 16 digit angka.", "error")
        return None
    return (nis, kosong("nisn"), nik, nama, jk, kosong("tempat_lahir"), tanggal, int(kelas_id))


@bp.route("/admin/siswa/form", methods=["GET", "POST"])
@bp.route("/admin/siswa/form/<int:item_id>", methods=["GET", "POST"])
@login_required
def form_siswa(item_id=None):
    row = query("SELECT * FROM siswa WHERE id=%s", (item_id,), one=True) if item_id else None
    if item_id and not row:
        return _missing(row, "main.data_siswa")
    kelas = _kelas_siswa()
    if request.method == "POST":
        data = _isi_siswa()
        if data is None:
            return redirect(request.url)
        if item_id:
            execute(
                """UPDATE siswa SET nis=%s, nisn=%s, nik=%s, nama=%s, jenis_kelamin=%s,
                   tempat_lahir=%s, tanggal_lahir=%s, kelas_id=%s WHERE id=%s""",
                (*data, item_id),
            )
            flash("Data siswa diperbarui.", "success")
        else:
            execute(
                """INSERT INTO siswa (nis, nisn, nik, nama, jenis_kelamin, tempat_lahir, tanggal_lahir,
                   kelas_id, agama, status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'Islam','aktif')""",
                data,
            )
            flash("Peserta didik disimpan.", "success")
            if request.form.get("aksi") == "lagi":
                return redirect(url_for("main.form_siswa"))
        return redirect(url_for("main.data_siswa"))
    return render_template("form_siswa.html", row=row or {}, kelas=kelas, nav="siswa")


@bp.route("/admin/siswa/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_siswa(item_id):
    execute("DELETE FROM siswa WHERE id=%s", (item_id,))
    flash("Data siswa dihapus.", "success")
    return redirect(url_for("main.data_siswa"))


@bp.route("/admin/siswa/hapus-terpilih", methods=["POST"])
@login_required
def hapus_siswa_terpilih():
    ids = [int(nilai) for nilai in request.form.getlist("id") if str(nilai).isdigit()]
    if not ids:
        flash("Pilih peserta didik yang akan dihapus.", "error")
        return redirect(url_for("main.data_siswa"))
    tanda = ", ".join(["%s"] * len(ids))
    execute(f"DELETE FROM siswa WHERE id IN ({tanda})", ids)
    flash(f"{len(ids)} peserta didik dihapus.", "success")
    return redirect(url_for("main.data_siswa"))


# ---------- Kelompok mapel ----------
def _kelompok_terpakai(item_id):
    try:
        return bool(query("SELECT COUNT(*) AS n FROM mata_pelajaran WHERE kelompok_id=%s", (item_id,), one=True)["n"])
    except Exception:
        return False


def _isi_kelompok(item_id=None):
    kode = (request.form.get("kode") or "").strip()
    nama = (request.form.get("nama") or "").strip()
    if not kode or not nama:
        flash("Kelompok dan nama kelompok wajib diisi.", "error")
        return None
    ada = query("SELECT id FROM kelompok_mapel WHERE kode=%s", (kode,), one=True)
    if ada and ada["id"] != item_id:
        flash("Kode kelompok itu sudah dipakai.", "error")
        return None
    return kode, nama


@bp.route("/admin/kelompok-mapel")
@login_required
def data_kelompok():
    q = (request.args.get("q") or "").strip()
    per = request.args.get("per", 10, type=int) or 10
    if per not in (10, 25, 50, 100):
        per = 10
    halaman = request.args.get("halaman", 1, type=int) or 1
    if halaman < 1:
        halaman = 1
    urut = request.args.get("urut") or "kode"
    arah = "DESC" if request.args.get("arah") == "desc" else "ASC"
    where = ""
    params = []
    if q:
        where = "WHERE kode LIKE %s OR nama LIKE %s"
        like = f"%{q}%"
        params = [like, like]
    order = f"nama {arah}, kode" if urut == "nama" else f"kode {arah}, nama"
    if urut != "nama":
        urut = "kode"
    total = query(f"SELECT COUNT(*) AS n FROM kelompok_mapel {where}", params, one=True)["n"]
    halaman_max = max((total + per - 1) // per, 1)
    if halaman > halaman_max:
        halaman = halaman_max
    awal = 0 if total == 0 else (halaman - 1) * per + 1
    rows = query(
        f"SELECT id, kode, nama, urutan FROM kelompok_mapel {where} ORDER BY {order} LIMIT %s OFFSET %s",
        (*params, per, (halaman - 1) * per),
    )
    akhir = 0 if total == 0 else awal + len(rows) - 1
    return render_template(
        "list_kelompok.html",
        rows=rows,
        q=q,
        per=per,
        halaman=halaman,
        total=total,
        awal=awal,
        akhir=akhir,
        urut=urut,
        arah=arah.lower(),
        nav="kelompok",
    )


@bp.route("/admin/kelompok-mapel/form", methods=["GET", "POST"])
@bp.route("/admin/kelompok-mapel/form/<int:item_id>", methods=["GET", "POST"])
@login_required
def form_kelompok(item_id=None):
    row = query("SELECT * FROM kelompok_mapel WHERE id=%s", (item_id,), one=True) if item_id else None
    if item_id and not row:
        return _missing(row, "main.data_kelompok")
    if request.method == "POST":
        data = _isi_kelompok(item_id)
        if data is None:
            return redirect(request.url)
        if item_id:
            execute("UPDATE kelompok_mapel SET kode=%s, nama=%s WHERE id=%s", (*data, item_id))
            flash("Kelompok mapel diperbarui.", "success")
        else:
            urutan = query("SELECT COALESCE(MAX(urutan), 0) AS n FROM kelompok_mapel", one=True)["n"] + 1
            execute(
                "INSERT INTO kelompok_mapel (kode, nama, urutan) VALUES (%s,%s,%s)",
                (*data, urutan),
            )
            flash("Kelompok mapel disimpan.", "success")
            if request.form.get("aksi") == "lagi":
                return redirect(url_for("main.form_kelompok"))
        return redirect(url_for("main.data_kelompok"))
    return render_template("form_kelompok.html", row=row or {}, nav="kelompok")


@bp.route("/admin/kelompok-mapel/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_kelompok(item_id):
    if _kelompok_terpakai(item_id):
        flash("Kelompok masih dipakai mata pelajaran. Lepaskan dulu sebelum menghapus.", "error")
        return redirect(url_for("main.data_kelompok"))
    execute("DELETE FROM kelompok_mapel WHERE id=%s", (item_id,))
    flash("Kelompok mapel dihapus.", "success")
    return redirect(url_for("main.data_kelompok"))


@bp.route("/admin/kelompok-mapel/hapus-terpilih", methods=["POST"])
@login_required
def hapus_kelompok_terpilih():
    ids = [int(nilai) for nilai in request.form.getlist("id") if str(nilai).isdigit()]
    if not ids:
        flash("Pilih kelompok yang akan dihapus.", "error")
        return redirect(url_for("main.data_kelompok"))
    terhapus = 0
    terpakai = 0
    for item_id in ids:
        if _kelompok_terpakai(item_id):
            terpakai += 1
            continue
        execute("DELETE FROM kelompok_mapel WHERE id=%s", (item_id,))
        terhapus += 1
    if terhapus:
        flash(f"{terhapus} kelompok mapel dihapus.", "success")
    if terpakai:
        flash(f"{terpakai} kelompok masih dipakai dan tidak dihapus.", "error")
    return redirect(url_for("main.data_kelompok"))


# ---------- Mapel ----------
def _kode_mapel_baru():
    rows = query("SELECT kode FROM mata_pelajaran")
    angka = [int(row["kode"]) for row in rows if str(row["kode"] or "").isdigit()]
    return str(max(angka) + 1) if angka else "900000001"


def _mapel_terpakai(item_id):
    for sql in (
        "SELECT COUNT(*) AS n FROM pelajaran WHERE mapel_id=%s",
        "SELECT COUNT(*) AS n FROM gabung_mapel_item WHERE mapel_id=%s",
        "SELECT COUNT(*) AS n FROM mapping_rapor WHERE mapel_id=%s",
    ):
        try:
            if query(sql, (item_id,), one=True)["n"]:
                return True
        except Exception:
            continue
    return False


@bp.route("/admin/mapel")
@login_required
def data_mapel():
    q = (request.args.get("q") or "").strip()
    per = request.args.get("per", 10, type=int) or 10
    if per not in (10, 25, 50, 100):
        per = 10
    halaman = request.args.get("halaman", 1, type=int) or 1
    if halaman < 1:
        halaman = 1
    urut = request.args.get("urut") or "kode"
    arah = "DESC" if request.args.get("arah") == "desc" else "ASC"
    where = ""
    params = []
    if q:
        where = "WHERE m.kode LIKE %s OR m.nama LIKE %s"
        like = f"%{q}%"
        params = [like, like]
    if urut == "nama":
        order = f"m.nama {arah}, m.kode"
    else:
        urut = "kode"
        order = (
            "CASE WHEN m.kode REGEXP '^[0-9]+$' THEN CAST(m.kode AS UNSIGNED) ELSE 999999999 END "
            f"{arah}, m.kode {arah}"
        )
    total = query(f"SELECT COUNT(*) AS n FROM mata_pelajaran m {where}", params, one=True)["n"]
    halaman_max = max((total + per - 1) // per, 1)
    if halaman > halaman_max:
        halaman = halaman_max
    awal = 0 if total == 0 else (halaman - 1) * per + 1
    rows = query(
        f"""SELECT m.id, m.kode, m.nama FROM mata_pelajaran m
            {where} ORDER BY {order} LIMIT %s OFFSET %s""",
        (*params, per, (halaman - 1) * per),
    )
    akhir = 0 if total == 0 else awal + len(rows) - 1
    return render_template(
        "list_mapel.html",
        rows=rows,
        q=q,
        per=per,
        halaman=halaman,
        total=total,
        awal=awal,
        akhir=akhir,
        urut=urut,
        arah=arah.lower(),
        nav="mapel",
    )


@bp.route("/admin/mapel/form", methods=["GET", "POST"])
@bp.route("/admin/mapel/form/<int:item_id>", methods=["GET", "POST"])
@login_required
def form_mapel(item_id=None):
    row = query("SELECT * FROM mata_pelajaran WHERE id=%s", (item_id,), one=True) if item_id else None
    if item_id and not row:
        return _missing(row, "main.data_mapel")
    if request.method == "POST":
        nama = (request.form.get("nama") or "").strip()
        if not nama:
            flash("Nama mata pelajaran wajib diisi.", "error")
            return redirect(request.url)
        if item_id:
            execute("UPDATE mata_pelajaran SET nama=%s WHERE id=%s", (nama, item_id))
            flash("Mata pelajaran diperbarui.", "success")
        else:
            kode = (request.form.get("kode") or "").strip()
            if not kode.isdigit() or query("SELECT id FROM mata_pelajaran WHERE kode=%s", (kode,), one=True):
                kode = _kode_mapel_baru()
            execute(
                "INSERT INTO mata_pelajaran (kode, nama, kkm_default) VALUES (%s,%s,75)",
                (kode, nama),
            )
            flash("Mata pelajaran disimpan.", "success")
            if request.form.get("aksi") == "lagi":
                return redirect(url_for("main.form_mapel"))
        return redirect(url_for("main.data_mapel"))
    return render_template(
        "form_mapel.html",
        row=row or {},
        kode=(row or {}).get("kode") or _kode_mapel_baru(),
        nav="mapel",
    )


@bp.route("/admin/mapel/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_mapel(item_id):
    if _mapel_terpakai(item_id):
        flash("Mata pelajaran masih dipakai. Lepaskan dulu sebelum menghapus.", "error")
        return redirect(url_for("main.data_mapel"))
    execute("DELETE FROM mata_pelajaran WHERE id=%s", (item_id,))
    flash("Mata pelajaran dihapus.", "success")
    return redirect(url_for("main.data_mapel"))


@bp.route("/admin/mapel/hapus-terpilih", methods=["POST"])
@login_required
def hapus_mapel_terpilih():
    ids = [int(nilai) for nilai in request.form.getlist("id") if str(nilai).isdigit()]
    if not ids:
        flash("Pilih mata pelajaran yang akan dihapus.", "error")
        return redirect(url_for("main.data_mapel"))
    terhapus = 0
    terpakai = 0
    for item_id in ids:
        if _mapel_terpakai(item_id):
            terpakai += 1
            continue
        execute("DELETE FROM mata_pelajaran WHERE id=%s", (item_id,))
        terhapus += 1
    if terhapus:
        flash(f"{terhapus} mata pelajaran dihapus.", "success")
    if terpakai:
        flash(f"{terpakai} mata pelajaran masih dipakai dan tidak dihapus.", "error")
    return redirect(url_for("main.data_mapel"))


# ---------- Pelajaran / pembelajaran ----------
_GURU_NAMA = (
    "TRIM(CONCAT("
    "IF(g.gelar_depan IS NULL OR g.gelar_depan='', '', CONCAT(g.gelar_depan, ' ')),"
    "IFNULL(g.nama, ''),"
    "IF(g.gelar_belakang IS NULL OR g.gelar_belakang='', '', CONCAT(', ', g.gelar_belakang))"
    "))"
)


def _isi_pelajaran():
    kelas_id = request.form.get("kelas_id") or ""
    mapel_id = request.form.get("mapel_id") or ""
    guru_id = request.form.get("guru_id") or ""
    if not kelas_id.isdigit() or not mapel_id.isdigit():
        flash("Rombongan belajar dan mata pelajaran wajib dipilih.", "error")
        return None
    if guru_id and not guru_id.isdigit():
        flash("Guru pengajar tidak valid.", "error")
        return None
    jam_teks = (request.form.get("jam_per_minggu") or "").strip()
    if not jam_teks:
        jam = None
    else:
        try:
            jam = int(jam_teks)
        except ValueError:
            flash("Jam mengajar per minggu harus berupa angka.", "error")
            return None
        if jam < 0:
            flash("Jam mengajar per minggu tidak boleh kurang dari 0.", "error")
            return None
    status = (request.form.get("status_kurikulum") or "").strip() or None
    return int(kelas_id), int(mapel_id), int(guru_id) if guru_id else None, jam, status


@bp.route("/admin/pelajaran")
@login_required
def data_pelajaran():
    q = (request.args.get("q") or "").strip()
    per = request.args.get("per", 10, type=int) or 10
    if per not in (10, 25, 50, 100):
        per = 10
    halaman = request.args.get("halaman", 1, type=int) or 1
    if halaman < 1:
        halaman = 1
    urut = request.args.get("urut") or "kelas"
    arah = "DESC" if request.args.get("arah") == "desc" else "ASC"
    ta_id = _ta_id()
    where = ["p.tahun_ajaran_id=%s"]
    params = [ta_id or 0]
    if not _admin_sekolah():
        where.append("p.guru_id=%s")
        params.append(session.get("guru_id") or 0)
    if q:
        where.append("(k.nama LIKE %s OR m.nama LIKE %s OR g.nama LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like])
    if urut == "mapel":
        order = f"m.nama {arah}, k.nama"
    elif urut == "guru":
        order = f"guru_nama {arah}, m.nama"
    elif urut == "jam":
        order = f"p.jam_per_minggu {arah}, m.nama"
    else:
        urut = "kelas"
        order = f"{ORDER_KELAS_K} {arah}, m.nama"
    saring = " AND ".join(where)
    total = query(
        f"""SELECT COUNT(*) AS n FROM pelajaran p
            JOIN kelas k ON k.id=p.kelas_id
            JOIN mata_pelajaran m ON m.id=p.mapel_id
            LEFT JOIN guru g ON g.id=p.guru_id
            WHERE {saring}""",
        params,
        one=True,
    )["n"] if ta_id else 0
    halaman_max = max((total + per - 1) // per, 1)
    if halaman > halaman_max:
        halaman = halaman_max
    awal = 0 if total == 0 else (halaman - 1) * per + 1
    rows = query(
        f"""SELECT p.id, p.jam_per_minggu, k.nama AS kelas_nama, m.nama AS mapel_nama,
                   {_GURU_NAMA} AS guru_nama
            FROM pelajaran p
            JOIN kelas k ON k.id=p.kelas_id
            JOIN mata_pelajaran m ON m.id=p.mapel_id
            LEFT JOIN guru g ON g.id=p.guru_id
            WHERE {saring} ORDER BY {order} LIMIT %s OFFSET %s""",
        (*params, per, (halaman - 1) * per),
    ) if ta_id else []
    akhir = 0 if total == 0 else awal + len(rows) - 1
    return render_template(
        "list_pelajaran.html",
        rows=rows,
        q=q,
        per=per,
        halaman=halaman,
        total=total,
        awal=awal,
        akhir=akhir,
        urut=urut,
        arah=arah.lower(),
        nav="pelajaran",
    )


@bp.route("/admin/pelajaran/form", methods=["GET", "POST"])
@bp.route("/admin/pelajaran/form/<int:item_id>", methods=["GET", "POST"])
@login_required
def form_pelajaran(item_id=None):
    import pymysql

    row = query("SELECT * FROM pelajaran WHERE id=%s", (item_id,), one=True) if item_id else None
    if item_id and not row:
        return _missing(row, "main.data_pelajaran")
    kelas = query(f"SELECT id, nama FROM kelas ORDER BY {ORDER_KELAS}")
    mapel = query("SELECT id, nama FROM mata_pelajaran ORDER BY nama")
    guru = query(
        f"""SELECT id, {_GURU_NAMA} AS nama FROM guru g
            WHERE aktif=1 OR id=%s ORDER BY nama""",
        ((row or {}).get("guru_id") or 0,),
    )
    if request.method == "POST":
        ta_id = _ta_id()
        if not ta_id:
            flash("Tahun ajaran aktif belum diatur.", "error")
            return redirect(url_for("main.data_pelajaran"))
        data = _isi_pelajaran()
        if data is None:
            return redirect(request.url)
        try:
            if item_id:
                execute(
                    """UPDATE pelajaran SET tahun_ajaran_id=%s, kelas_id=%s, mapel_id=%s, guru_id=%s,
                       jam_per_minggu=%s, status_kurikulum=%s WHERE id=%s""",
                    (ta_id, *data, item_id),
                )
                flash("Pembelajaran diperbarui.", "success")
            else:
                kode = (request.form.get("kode") or "").strip() or str(uuid4())
                execute(
                    """INSERT INTO pelajaran
                       (kode, tahun_ajaran_id, kelas_id, mapel_id, guru_id, jam_per_minggu, status_kurikulum)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (kode, ta_id, *data),
                )
                flash("Pembelajaran disimpan.", "success")
                if request.form.get("aksi") == "lagi":
                    return redirect(url_for("main.form_pelajaran"))
        except pymysql.err.IntegrityError:
            flash("Mapel itu sudah terdaftar di kelas yang sama pada tahun ajaran ini.", "error")
            return redirect(request.url)
        return redirect(url_for("main.data_pelajaran"))
    return render_template(
        "form_pelajaran.html",
        row=row or {},
        kode=(row or {}).get("kode") or str(uuid4()),
        kelas=kelas,
        mapel=mapel,
        guru=guru,
        nav="pelajaran",
    )


@bp.route("/admin/pelajaran/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_pelajaran(item_id):
    execute("DELETE FROM pelajaran WHERE id=%s", (item_id,))
    flash("Pembelajaran dihapus.", "success")
    return redirect(url_for("main.data_pelajaran"))


@bp.route("/admin/pelajaran/hapus-terpilih", methods=["POST"])
@login_required
def hapus_pelajaran_terpilih():
    ids = [int(nilai) for nilai in request.form.getlist("id") if str(nilai).isdigit()]
    if not ids:
        flash("Pilih pembelajaran yang akan dihapus.", "error")
        return redirect(url_for("main.data_pelajaran"))
    tanda = ", ".join(["%s"] * len(ids))
    execute(f"DELETE FROM pelajaran WHERE id IN ({tanda})", ids)
    flash(f"{len(ids)} pembelajaran dihapus.", "success")
    return redirect(url_for("main.data_pelajaran"))


# ---------- Gabung mapel ----------
@bp.route("/admin/gabung-mapel")
@login_required
def gabung_mapel():
    q = (request.args.get("q") or "").strip()
    per = request.args.get("per", 10, type=int) or 10
    if per not in (10, 25, 50, 100):
        per = 10
    halaman = request.args.get("halaman", 1, type=int) or 1
    if halaman < 1:
        halaman = 1
    arah = "DESC" if request.args.get("arah") == "desc" else "ASC"
    where = ""
    params = []
    if q:
        where = "WHERE nama_gabungan LIKE %s"
        params = [f"%{q}%"]
    total = query(f"SELECT COUNT(*) AS n FROM gabung_mapel {where}", params, one=True)["n"]
    halaman_max = max((total + per - 1) // per, 1)
    if halaman > halaman_max:
        halaman = halaman_max
    awal = 0 if total == 0 else (halaman - 1) * per + 1
    rows = query(
        f"""SELECT id, nama_gabungan FROM gabung_mapel {where}
            ORDER BY nama_gabungan {arah}, id LIMIT %s OFFSET %s""",
        (*params, per, (halaman - 1) * per),
    )
    akhir = 0 if total == 0 else awal + len(rows) - 1
    return render_template(
        "list_gabung.html",
        rows=rows,
        q=q,
        per=per,
        halaman=halaman,
        total=total,
        awal=awal,
        akhir=akhir,
        arah=arah.lower(),
        nav="gabung",
    )


@bp.route("/admin/gabung-mapel/form", methods=["GET", "POST"])
@bp.route("/admin/gabung-mapel/form/<int:item_id>", methods=["GET", "POST"])
@login_required
def form_gabung(item_id=None):
    row = query("SELECT * FROM gabung_mapel WHERE id=%s", (item_id,), one=True) if item_id else None
    if item_id and not row:
        return _missing(row, "main.gabung_mapel")
    if request.method == "POST":
        nama = (request.form.get("nama_gabungan") or "").strip()
        if not nama:
            flash("Nama penggabungan mapel wajib diisi.", "error")
            return redirect(request.url)
        if item_id:
            execute("UPDATE gabung_mapel SET nama_gabungan=%s WHERE id=%s", (nama, item_id))
            flash("Gabungan mapel diperbarui.", "success")
        else:
            execute("INSERT INTO gabung_mapel (nama_gabungan) VALUES (%s)", (nama,))
            flash("Gabungan mapel disimpan.", "success")
            if request.form.get("aksi") == "lagi":
                return redirect(url_for("main.form_gabung"))
        return redirect(url_for("main.gabung_mapel"))
    return render_template("form_gabung.html", row=row or {}, nav="gabung")


@bp.route("/admin/gabung-mapel/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_gabung(item_id):
    execute("DELETE FROM gabung_mapel WHERE id=%s", (item_id,))
    flash("Gabungan mapel dihapus.", "success")
    return redirect(url_for("main.gabung_mapel"))


# ---------- Mapping rapor ----------
def _filter_mapping():
    kurikulum = request.args.get("kurikulum") or request.form.get("kurikulum") or ""
    tingkat = request.args.get("tingkat") or request.form.get("tingkat") or ""
    q = (request.args.get("q") or request.form.get("q") or "").strip()
    if kurikulum not in KURIKULUM_SEKOLAH:
        kurikulum = ""
    if tingkat not in TINGKAT_KELAS:
        tingkat = ""
    if not request.args and not request.form:
        kurikulum, tingkat = "Kurikulum Merdeka", "7"
    if request.values.get("kosong"):
        kurikulum, tingkat = "", ""
    return kurikulum, tingkat, q


def _kembali_mapping():
    kurikulum, tingkat, q = _filter_mapping()
    return redirect(url_for(
        "main.mapping_rapor",
        kurikulum=kurikulum,
        tingkat=tingkat,
        q=q,
        per=request.values.get("per") or 10,
        urut=request.values.get("urut") or "",
        arah=request.values.get("arah") or "asc",
        kosong=1 if request.values.get("kosong") else None,
    ))


@bp.route("/admin/mapping-rapor")
@login_required
def mapping_rapor():
    kurikulum, tingkat, q = _filter_mapping()
    per = request.args.get("per", 10, type=int) or 10
    if per not in (10, 25, 50, 100):
        per = 10
    halaman = request.args.get("halaman", 1, type=int) or 1
    if halaman < 1:
        halaman = 1
    urut = request.args.get("urut") or "urutan"
    arah = "DESC" if request.args.get("arah") == "desc" else "ASC"
    where = ["1=1"]
    params = []
    if kurikulum:
        where.append("mr.kurikulum=%s")
        params.append(kurikulum)
    if tingkat:
        where.append("mr.tingkat=%s")
        params.append(tingkat)
    if q:
        where.append("(m.nama LIKE %s OR mr.nama_lokal LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like])
    saring = " AND ".join(where)
    order = f"m.nama {arah}, mr.urutan" if urut == "nama" else f"mr.urutan {arah}, m.nama"
    if urut != "nama":
        urut = "urutan"
    total = query(
        f"""SELECT COUNT(*) AS n FROM mapping_rapor mr
            JOIN mata_pelajaran m ON m.id=mr.mapel_id
            WHERE {saring}""",
        params,
        one=True,
    )["n"]
    halaman_max = max((total + per - 1) // per, 1)
    if halaman > halaman_max:
        halaman = halaman_max
    awal = 0 if total == 0 else (halaman - 1) * per + 1
    rows = query(
        f"""SELECT mr.id, mr.nama_lokal, mr.urutan, mr.kelompok_id, mr.kurikulum, mr.tingkat,
                   m.nama AS mapel_nama
            FROM mapping_rapor mr
            JOIN mata_pelajaran m ON m.id=mr.mapel_id
            WHERE {saring}
            ORDER BY {order} LIMIT %s OFFSET %s""",
        (*params, per, (halaman - 1) * per),
    )
    akhir = 0 if total == 0 else awal + len(rows) - 1
    return render_template(
        "mapping_rapor.html",
        rows=rows,
        kelompok=query("SELECT id, nama FROM kelompok_mapel ORDER BY urutan, nama"),
        kurikulum=kurikulum,
        tingkat=tingkat,
        kurikulum_opsi=KURIKULUM_SEKOLAH,
        tingkat_opsi=TINGKAT_KELAS,
        q=q,
        per=per,
        halaman=halaman,
        total=total,
        awal=awal,
        akhir=akhir,
        urut=urut,
        arah=arah.lower(),
        saring=int(bool(kurikulum)) + int(bool(tingkat)),
        nav="mapping",
    )


@bp.route("/admin/mapping-rapor/form", methods=["GET", "POST"])
@login_required
def form_mapping():
    mapel = query("SELECT id, nama, kelompok_id FROM mata_pelajaran ORDER BY nama")
    kelompok = query("SELECT id, nama FROM kelompok_mapel ORDER BY urutan, nama")
    if request.method == "POST":
        kurikulum = request.form.get("kurikulum") or ""
        tingkat = request.form.get("tingkat") or ""
        mapel_id = request.form.get("mapel_id") or ""
        nama_lokal = (request.form.get("nama_lokal") or "").strip()
        kelompok_id = request.form.get("kelompok_id") or ""
        urutan_teks = (request.form.get("urutan") or "").strip()
        if kurikulum not in KURIKULUM_SEKOLAH or tingkat not in TINGKAT_KELAS or not mapel_id.isdigit() or not nama_lokal:
            flash("Kurikulum, tingkat, mata pelajaran, dan nama lokal wajib diisi.", "error")
            return redirect(request.url)
        if not urutan_teks.isdigit():
            flash("No urut rapor wajib berupa angka.", "error")
            return redirect(request.url)
        if kelompok_id and not kelompok_id.isdigit():
            kelompok_id = ""
        if query(
            "SELECT id FROM mapping_rapor WHERE kurikulum=%s AND tingkat=%s AND mapel_id=%s",
            (kurikulum, tingkat, int(mapel_id)),
            one=True,
        ):
            flash("Mata pelajaran itu sudah dimapping pada kurikulum dan tingkat yang sama.", "error")
            return redirect(request.url)
        execute(
            """INSERT INTO mapping_rapor
               (mapel_id, tampil_rapor, urutan, kurikulum, tingkat, nama_lokal, kelompok_id)
               VALUES (%s,1,%s,%s,%s,%s,%s)""",
            (int(mapel_id), int(urutan_teks), kurikulum, tingkat, nama_lokal, int(kelompok_id) if kelompok_id else None),
        )
        flash("Mapping rapor disimpan.", "success")
        if request.form.get("aksi") == "lagi":
            return redirect(url_for("main.form_mapping"))
        return redirect(url_for("main.mapping_rapor", kurikulum=kurikulum, tingkat=tingkat))
    return render_template(
        "form_mapping.html",
        mapel=mapel,
        kelompok=kelompok,
        kurikulum_opsi=KURIKULUM_SEKOLAH,
        tingkat_opsi=TINGKAT_KELAS,
        nav="mapping",
    )


@bp.route("/admin/mapping-rapor/ubah/<int:item_id>", methods=["POST"])
@login_required
def ubah_mapping(item_id):
    if "nama_lokal" in request.form:
        nama = (request.form.get("nama_lokal") or "").strip()
        if not nama:
            flash("Nama lokal wajib diisi.", "error")
        else:
            execute("UPDATE mapping_rapor SET nama_lokal=%s WHERE id=%s", (nama, item_id))
    if "kelompok_id" in request.form:
        kelompok_id = request.form.get("kelompok_id") or ""
        execute(
            "UPDATE mapping_rapor SET kelompok_id=%s WHERE id=%s",
            (int(kelompok_id) if kelompok_id.isdigit() else None, item_id),
        )
    if "urutan" in request.form:
        urutan_teks = (request.form.get("urutan") or "").strip()
        if urutan_teks.isdigit():
            execute("UPDATE mapping_rapor SET urutan=%s WHERE id=%s", (int(urutan_teks), item_id))
        else:
            flash("No urut rapor wajib berupa angka.", "error")
    return _kembali_mapping()


@bp.route("/admin/mapping-rapor/hapus", methods=["POST"])
@login_required
def hapus_mapping():
    ids = [int(nilai) for nilai in request.form.getlist("id") if str(nilai).isdigit()]
    if not ids:
        flash("Pilih mapping yang akan dihapus.", "error")
        return _kembali_mapping()
    tanda = ", ".join(["%s"] * len(ids))
    execute(f"DELETE FROM mapping_rapor WHERE id IN ({tanda})", ids)
    flash(f"{len(ids)} mapping rapor dihapus.", "success")
    return _kembali_mapping()


# ---------- Ekskul ----------
def _kode_semester():
    ta = query("SELECT tahun, semester FROM tahun_ajaran WHERE aktif=1 LIMIT 1", one=True)
    if not ta:
        return "-"
    angka = "".join(ch for ch in str(ta["tahun"] or "") if ch.isdigit())
    awal = angka[:4]
    if not awal:
        return str(ta["semester"] or "-")
    return f"{awal}{ta['semester'] or ''}"


def _nama_guru(guru_id):
    if not guru_id:
        return ""
    row = query(f"SELECT {_GURU_NAMA} AS nama FROM guru g WHERE id=%s", (guru_id,), one=True)
    return (row or {}).get("nama") or ""


def _isi_ekskul():
    nama = (request.form.get("nama") or "").strip()
    if not nama:
        flash("Nama ekskul wajib diisi.", "error")
        return None
    pembina_id = request.form.get("pembina_id") or ""
    if pembina_id and not pembina_id.isdigit():
        pembina_id = ""
    nama_pembina = (request.form.get("nama_pembina") or "").strip()
    if pembina_id and not nama_pembina:
        nama_pembina = _nama_guru(int(pembina_id))
    return nama, int(pembina_id) if pembina_id else None, nama_pembina or None


@bp.route("/admin/ekskul")
@login_required
def data_ekskul():
    q = (request.args.get("q") or "").strip()
    pembina = request.args.get("pembina_id") or ""
    if not pembina.isdigit():
        pembina = ""
    per = request.args.get("per", 10, type=int) or 10
    if per not in (10, 25, 50, 100):
        per = 10
    halaman = request.args.get("halaman", 1, type=int) or 1
    if halaman < 1:
        halaman = 1
    urut = request.args.get("urut") or "nama"
    arah = "DESC" if request.args.get("arah") == "desc" else "ASC"
    where = ["1=1"]
    params = []
    if not _admin_sekolah():
        where.append("e.pembina_id=%s")
        params.append(session.get("guru_id") or 0)
    if q:
        where.append("(e.nama LIKE %s OR e.nama_pembina LIKE %s OR g.nama LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like])
    if pembina:
        where.append("e.pembina_id=%s")
        params.append(int(pembina))
    if urut == "pembina":
        order = f"pembina {arah}, e.nama"
    elif urut == "peserta":
        order = f"peserta {arah}, e.nama"
    else:
        urut = "nama"
        order = f"e.nama {arah}"
    saring = " AND ".join(where)
    dari = """FROM ekstrakurikuler e
              LEFT JOIN guru g ON g.id=e.pembina_id"""
    total = query(f"SELECT COUNT(*) AS n {dari} WHERE {saring}", params, one=True)["n"]
    halaman_max = max((total + per - 1) // per, 1)
    if halaman > halaman_max:
        halaman = halaman_max
    awal = 0 if total == 0 else (halaman - 1) * per + 1
    rows = query(
        f"""SELECT e.id, e.nama, e.pembina_id,
                   COALESCE(NULLIF(e.nama_pembina, ''), {_GURU_NAMA}) AS pembina,
                   (SELECT COUNT(*) FROM peserta_ekskul p WHERE p.ekskul_id=e.id) AS peserta
            {dari}
            WHERE {saring}
            ORDER BY {order} LIMIT %s OFFSET %s""",
        (*params, per, (halaman - 1) * per),
    )
    akhir = 0 if total == 0 else awal + len(rows) - 1
    return render_template(
        "list_ekskul.html",
        rows=rows,
        guru=query(f"SELECT id, {_GURU_NAMA} AS nama FROM guru g WHERE aktif=1 ORDER BY nama"),
        q=q,
        pembina_id=pembina,
        per=per,
        halaman=halaman,
        total=total,
        awal=awal,
        akhir=akhir,
        urut=urut,
        arah=arah.lower(),
        semester=_kode_semester(),
        saring=int(bool(pembina)),
        nav="ekskul",
    )


@bp.route("/admin/ekskul/form", methods=["GET", "POST"])
@bp.route("/admin/ekskul/form/<int:item_id>", methods=["GET", "POST"])
@login_required
def form_ekskul(item_id=None):
    row = query("SELECT * FROM ekstrakurikuler WHERE id=%s", (item_id,), one=True) if item_id else None
    if item_id and not row:
        return _missing(row, "main.data_ekskul")
    guru = query(f"SELECT id, {_GURU_NAMA} AS nama FROM guru g WHERE aktif=1 OR id=%s ORDER BY nama", ((row or {}).get("pembina_id") or 0,))
    if request.method == "POST":
        data = _isi_ekskul()
        if data is None:
            return redirect(request.url)
        if item_id:
            execute(
                "UPDATE ekstrakurikuler SET nama=%s, pembina_id=%s, nama_pembina=%s WHERE id=%s",
                (*data, item_id),
            )
            flash("Ekstrakurikuler diperbarui.", "success")
        else:
            execute(
                "INSERT INTO ekstrakurikuler (nama, pembina_id, nama_pembina) VALUES (%s,%s,%s)",
                data,
            )
            flash("Ekstrakurikuler disimpan.", "success")
            if request.form.get("aksi") == "lagi":
                return redirect(url_for("main.form_ekskul"))
        return redirect(url_for("main.data_ekskul"))
    return render_template("form_ekskul.html", row=row or {}, guru=guru, nav="ekskul")


@bp.route("/admin/ekskul/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_ekskul(item_id):
    execute("DELETE FROM ekstrakurikuler WHERE id=%s", (item_id,))
    flash("Ekstrakurikuler dihapus.", "success")
    return redirect(url_for("main.data_ekskul"))


@bp.route("/admin/ekskul/hapus-terpilih", methods=["POST"])
@login_required
def hapus_ekskul_terpilih():
    ids = [int(nilai) for nilai in request.form.getlist("id") if str(nilai).isdigit()]
    if not ids:
        flash("Pilih ekstra kurikuler yang akan dihapus.", "error")
        return redirect(url_for("main.data_ekskul"))
    tanda = ", ".join(["%s"] * len(ids))
    execute(f"DELETE FROM ekstrakurikuler WHERE id IN ({tanda})", ids)
    flash(f"{len(ids)} ekstra kurikuler dihapus.", "success")
    return redirect(url_for("main.data_ekskul"))


@bp.route("/admin/ekskul/<int:item_id>/peserta", methods=["GET", "POST"])
@login_required
def peserta_ekskul(item_id):
    ekskul = query("SELECT * FROM ekstrakurikuler WHERE id=%s", (item_id,), one=True)
    if not ekskul:
        return _missing(ekskul, "main.data_ekskul")
    if not _admin_sekolah() and ekskul["pembina_id"] != session.get("guru_id"):
        flash("Ekstrakurikuler ini bukan tugas Anda.", "error")
        return redirect(url_for("main.data_ekskul"))
    kelas_id = request.values.get("kelas_id") or ""
    if not str(kelas_id).isdigit():
        kelas_id = ""
    if request.method == "POST" and kelas_id:
        dipilih = {int(nilai) for nilai in request.form.getlist("siswa_id") if str(nilai).isdigit()}
        siswa_kelas = query("SELECT id FROM siswa WHERE kelas_id=%s", (int(kelas_id),))
        for siswa in siswa_kelas:
            if siswa["id"] in dipilih:
                ada = query(
                    "SELECT id FROM peserta_ekskul WHERE ekskul_id=%s AND siswa_id=%s",
                    (item_id, siswa["id"]),
                    one=True,
                )
                if not ada:
                    execute(
                        "INSERT INTO peserta_ekskul (ekskul_id, siswa_id) VALUES (%s,%s)",
                        (item_id, siswa["id"]),
                    )
            else:
                execute(
                    "DELETE FROM peserta_ekskul WHERE ekskul_id=%s AND siswa_id=%s",
                    (item_id, siswa["id"]),
                )
        flash("Peserta ekskul disimpan.", "success")
        return redirect(url_for("main.peserta_ekskul", item_id=item_id, kelas_id=kelas_id))
    anggota = query(
        f"""SELECT s.id, s.nama, s.nis, k.nama AS kelas_nama
            FROM peserta_ekskul p
            JOIN siswa s ON s.id=p.siswa_id
            LEFT JOIN kelas k ON k.id=s.kelas_id
            WHERE p.ekskul_id=%s
            ORDER BY {ORDER_KELAS_K}, s.nama""",
        (item_id,),
    )
    calon = []
    if kelas_id:
        calon = query(
            """SELECT s.id, s.nama, s.nis,
                      EXISTS(SELECT 1 FROM peserta_ekskul p WHERE p.ekskul_id=%s AND p.siswa_id=s.id) AS ikut
               FROM siswa s WHERE s.kelas_id=%s ORDER BY s.nama""",
            (item_id, int(kelas_id)),
        )
    return render_template(
        "peserta_ekskul.html",
        ekskul=ekskul,
        anggota=anggota,
        calon=calon,
        kelas=query(f"SELECT id, nama FROM kelas ORDER BY {ORDER_KELAS}"),
        kelas_id=kelas_id,
        nav="ekskul",
    )


# ---------- Tryout ----------
@bp.route("/admin/tryout", methods=["GET", "POST"])
@login_required
def data_tryout():
    if request.method == "POST":
        execute(
            "INSERT INTO tryout (nama, tanggal, tingkat) VALUES (%s,%s,%s)",
            (request.form.get("nama"), request.form.get("tanggal") or None, request.form.get("tingkat") if request.form.get("tingkat") in TINGKAT_KELAS else "9"),
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
           LEFT JOIN guru g ON g.id=pel.guru_id
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
def _isi_aspek():
    nama = (request.form.get("nama") or "").strip()
    if not nama:
        flash("Nama aspek wajib diisi.", "error")
        return None
    if len(nama) > 150:
        flash("Nama aspek terlalu panjang.", "error")
        return None
    mentah = (request.form.get("urutan") or "").strip()
    if not mentah:
        flash("Urutan tampilan wajib diisi.", "error")
        return None
    try:
        urutan = int(mentah)
    except ValueError:
        flash("Urutan tampilan harus angka.", "error")
        return None
    return nama, urutan, 1 if request.form.get("aktif") else 0


@bp.route("/admin/tahfiz/aspek")
@login_required
def aspek_tahfiz():
    q = (request.args.get("q") or "").strip()
    per = request.args.get("per", 10, type=int) or 10
    if per not in (10, 25, 50, 100):
        per = 10
    halaman = request.args.get("halaman", 1, type=int) or 1
    if halaman < 1:
        halaman = 1
    urut = "nama" if request.args.get("urut") == "nama" else "urutan"
    arah = "DESC" if request.args.get("arah") == "desc" else "ASC"
    where = ["1=1"]
    params = []
    if q:
        where.append("nama LIKE %s")
        params.append(f"%{q}%")
    saring = " AND ".join(where)
    order = f"nama {arah}, urutan, id" if urut == "nama" else f"urutan {arah}, id"
    total = query(f"SELECT COUNT(*) AS n FROM aspek_tahfiz WHERE {saring}", params, one=True)["n"]
    halaman_max = max((total + per - 1) // per, 1)
    if halaman > halaman_max:
        halaman = halaman_max
    awal = 0 if total == 0 else (halaman - 1) * per + 1
    rows = query(
        f"""SELECT id, nama, jenis, kkm, urutan, aktif, dibuat
            FROM aspek_tahfiz WHERE {saring}
            ORDER BY {order} LIMIT %s OFFSET %s""",
        (*params, per, (halaman - 1) * per),
    )
    akhir = 0 if total == 0 else awal + len(rows) - 1
    return render_template(
        "list_aspek.html",
        rows=rows,
        q=q,
        per=per,
        halaman=halaman,
        total=total,
        awal=awal,
        akhir=akhir,
        urut=urut,
        arah=arah.lower(),
        nav="aspek",
    )


@bp.route("/admin/tahfiz/aspek/form", methods=["GET", "POST"])
@bp.route("/admin/tahfiz/aspek/form/<int:item_id>", methods=["GET", "POST"])
@login_required
def form_aspek(item_id=None):
    row = query("SELECT * FROM aspek_tahfiz WHERE id=%s", (item_id,), one=True) if item_id else None
    if item_id and not row:
        return _missing(row, "main.aspek_tahfiz")
    if request.method == "POST":
        data = _isi_aspek()
        if data is None:
            return redirect(request.url)
        if item_id:
            execute(
                "UPDATE aspek_tahfiz SET nama=%s, urutan=%s, aktif=%s WHERE id=%s",
                (*data, item_id),
            )
            flash("Aspek tahfiz diperbarui.", "success")
        else:
            execute(
                "INSERT INTO aspek_tahfiz (nama, jenis, kkm, urutan, aktif, dibuat) VALUES (%s,'Hafalan',75,%s,%s,NOW())",
                data,
            )
            flash("Aspek tahfiz disimpan.", "success")
            if request.form.get("aksi") == "lagi":
                return redirect(url_for("main.form_aspek"))
        return redirect(url_for("main.aspek_tahfiz"))
    return render_template("form_aspek.html", row=row or {}, nav="aspek")


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


@bp.route("/admin/tahfiz/aspek/hapus-terpilih", methods=["POST"])
@login_required
def hapus_aspek_terpilih():
    ids = [int(nilai) for nilai in request.form.getlist("id") if str(nilai).isdigit()]
    if not ids:
        flash("Pilih aspek yang akan dihapus.", "error")
        return redirect(url_for("main.aspek_tahfiz"))
    bebas = []
    tertahan = 0
    for item_id in ids:
        dipakai = query(
            """SELECT (
                 (SELECT COUNT(*) FROM mapping_guru_tahfiz WHERE aspek_id=%s) +
                 (SELECT COUNT(*) FROM nilai_tahfiz WHERE aspek_id=%s)
               ) AS n""",
            (item_id, item_id),
            one=True,
        )["n"]
        if dipakai:
            tertahan += 1
        else:
            bebas.append(item_id)
    if bebas:
        tanda = ", ".join(["%s"] * len(bebas))
        execute(f"DELETE FROM aspek_tahfiz WHERE id IN ({tanda})", bebas)
        flash(f"{len(bebas)} aspek dihapus.", "success")
    if tertahan:
        flash("Sebagian aspek masih dipakai di mapping guru atau nilai tahfiz.", "error")
    return redirect(url_for("main.aspek_tahfiz"))


def _pasangan_mapping(guru_id, kelas_id, kecuali=None):
    sql = "SELECT id FROM mapping_guru_tahfiz WHERE guru_id=%s AND kelas_id=%s"
    params = [guru_id, kelas_id]
    if kecuali:
        sql += " AND NOT (guru_id=%s AND kelas_id=%s)"
        params.extend(kecuali)
    return query(sql, params, one=True)


def _isi_mapping_tahfiz():
    guru_id = request.form.get("guru_id") or ""
    kelas_id = request.form.get("kelas_id") or ""
    if not guru_id.isdigit() or not kelas_id.isdigit():
        flash("Guru dan rombel wajib dipilih.", "error")
        return None
    return int(guru_id), int(kelas_id)


@bp.route("/admin/tahfiz/mapping")
@login_required
def mapping_tahfiz():
    q = (request.args.get("q") or "").strip()
    per = request.args.get("per", 10, type=int) or 10
    if per not in (10, 25, 50, 100):
        per = 10
    halaman = request.args.get("halaman", 1, type=int) or 1
    if halaman < 1:
        halaman = 1
    urut = "kelas" if request.args.get("urut") == "kelas" else "guru"
    arah = "DESC" if request.args.get("arah") == "desc" else "ASC"
    where = ["1=1"]
    params = []
    if q:
        where.append(f"({_GURU_NAMA} LIKE %s OR k.nama LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like])
    saring = " AND ".join(where)
    order = f"k.nama {arah}, guru_nama" if urut == "kelas" else f"guru_nama {arah}, k.nama"
    dari = f"""FROM mapping_guru_tahfiz m
               JOIN guru g ON g.id=m.guru_id
               JOIN kelas k ON k.id=m.kelas_id
               WHERE {saring}"""
    total = query(
        f"SELECT COUNT(*) AS n FROM (SELECT m.guru_id, m.kelas_id {dari} GROUP BY m.guru_id, m.kelas_id) x",
        params,
        one=True,
    )["n"]
    halaman_max = max((total + per - 1) // per, 1)
    if halaman > halaman_max:
        halaman = halaman_max
    awal = 0 if total == 0 else (halaman - 1) * per + 1
    rows = query(
        f"""SELECT MIN(m.id) AS id, {_GURU_NAMA} AS guru_nama, k.nama AS kelas_nama, MIN(m.dibuat) AS dibuat
            {dari}
            GROUP BY m.guru_id, m.kelas_id, g.gelar_depan, g.nama, g.gelar_belakang, k.nama
            ORDER BY {order} LIMIT %s OFFSET %s""",
        (*params, per, (halaman - 1) * per),
    )
    akhir = 0 if total == 0 else awal + len(rows) - 1
    return render_template(
        "mapping_tahfiz.html",
        rows=rows,
        q=q,
        per=per,
        halaman=halaman,
        total=total,
        awal=awal,
        akhir=akhir,
        urut=urut,
        arah=arah.lower(),
        nav="maptahfiz",
    )


@bp.route("/admin/tahfiz/mapping/form", methods=["GET", "POST"])
@bp.route("/admin/tahfiz/mapping/form/<int:item_id>", methods=["GET", "POST"])
@login_required
def form_mapping_tahfiz(item_id=None):
    row = None
    if item_id:
        row = query(
            f"""SELECT m.id, m.guru_id, m.kelas_id
                FROM mapping_guru_tahfiz m WHERE m.id=%s""",
            (item_id,),
            one=True,
        )
        if not row:
            return _missing(row, "main.mapping_tahfiz")
    if request.method == "POST":
        data = _isi_mapping_tahfiz()
        if data is None:
            return redirect(request.url)
        guru_id, kelas_id = data
        if item_id:
            lama = query("SELECT guru_id, kelas_id FROM mapping_guru_tahfiz WHERE id=%s", (item_id,), one=True)
            if _pasangan_mapping(guru_id, kelas_id, (lama["guru_id"], lama["kelas_id"])):
                flash("Guru ini sudah dipetakan ke rombel tersebut.", "error")
                return redirect(request.url)
            execute(
                "UPDATE mapping_guru_tahfiz SET guru_id=%s, kelas_id=%s WHERE guru_id=%s AND kelas_id=%s",
                (guru_id, kelas_id, lama["guru_id"], lama["kelas_id"]),
            )
            flash("Mapping guru tahfiz diperbarui.", "success")
        else:
            if _pasangan_mapping(guru_id, kelas_id):
                flash("Guru ini sudah dipetakan ke rombel tersebut.", "error")
                return redirect(request.url)
            aspek = query("SELECT id FROM aspek_tahfiz WHERE aktif=1 ORDER BY urutan, id LIMIT 1", one=True)
            if not aspek:
                flash("Buat aspek tahfiz terlebih dahulu.", "error")
                return redirect(url_for("main.aspek_tahfiz"))
            execute(
                "INSERT INTO mapping_guru_tahfiz (guru_id, kelas_id, aspek_id, dibuat) VALUES (%s,%s,%s,NOW())",
                (guru_id, kelas_id, aspek["id"]),
            )
            flash("Mapping guru tahfiz disimpan.", "success")
            if request.form.get("aksi") == "lagi":
                return redirect(url_for("main.form_mapping_tahfiz"))
        return redirect(url_for("main.mapping_tahfiz"))
    guru = query(
        f"""SELECT id, {_GURU_NAMA} AS nama FROM guru g
            WHERE aktif=1 OR id=%s ORDER BY nama""",
        ((row or {}).get("guru_id") or 0,),
    )
    kelas = query(f"SELECT id, nama FROM kelas ORDER BY {ORDER_KELAS}")
    return render_template("form_mapping_tahfiz.html", row=row or {}, guru=guru, kelas=kelas, nav="maptahfiz")


@bp.route("/admin/tahfiz/mapping/hapus/<int:item_id>", methods=["POST"])
@login_required
def hapus_mapping_tahfiz(item_id):
    row = query("SELECT guru_id, kelas_id FROM mapping_guru_tahfiz WHERE id=%s", (item_id,), one=True)
    if row:
        execute(
            "DELETE FROM mapping_guru_tahfiz WHERE guru_id=%s AND kelas_id=%s",
            (row["guru_id"], row["kelas_id"]),
        )
    flash("Mapping dihapus.", "success")
    return redirect(url_for("main.mapping_tahfiz"))


@bp.route("/admin/tahfiz/mapping/hapus-terpilih", methods=["POST"])
@login_required
def hapus_mapping_tahfiz_terpilih():
    ids = [int(nilai) for nilai in request.form.getlist("id") if str(nilai).isdigit()]
    if not ids:
        flash("Pilih mapping yang akan dihapus.", "error")
        return redirect(url_for("main.mapping_tahfiz"))
    for item_id in ids:
        row = query("SELECT guru_id, kelas_id FROM mapping_guru_tahfiz WHERE id=%s", (item_id,), one=True)
        if row:
            execute(
                "DELETE FROM mapping_guru_tahfiz WHERE guru_id=%s AND kelas_id=%s",
                (row["guru_id"], row["kelas_id"]),
            )
    flash(f"{len(ids)} mapping dihapus.", "success")
    return redirect(url_for("main.mapping_tahfiz"))


def _teks_tanggal(nilai):
    if not nilai or not hasattr(nilai, "day"):
        return ""
    bulan = (
        "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    )
    return f"{nilai.day} {bulan[nilai.month]} {nilai.year}"


def _isi_pengaturan_tahfiz():
    bidang = {
        "tanggal_hijriah": "Tanggal Hijriah Rapor",
        "tanggal_masehi": "Tanggal Masehi Rapor",
        "tempat_cetak": "Tempat Cetak Rapor",
        "nama_kepala": "Nama Kepala Sekolah",
        "nbm_kepala": "NBM Kepala Sekolah",
    }
    batas = {
        "tanggal_hijriah": 80,
        "tanggal_masehi": 80,
        "tempat_cetak": 120,
        "nama_kepala": 150,
        "nbm_kepala": 40,
    }
    hasil = []
    for kunci, label in bidang.items():
        nilai = (request.form.get(kunci) or "").strip()
        if not nilai:
            flash(f"{label} wajib diisi.", "error")
            return None
        if len(nilai) > batas[kunci]:
            flash(f"{label} terlalu panjang.", "error")
            return None
        hasil.append(nilai)
    return tuple(hasil)


@bp.route("/admin/tahfiz/pengaturan", methods=["GET", "POST"])
@login_required
def pengaturan_tahfiz():
    if request.method == "POST":
        data = _isi_pengaturan_tahfiz()
        if data is None:
            return redirect(url_for("main.pengaturan_tahfiz"))
        row = query("SELECT id FROM pengaturan_rapor_tahfiz LIMIT 1", one=True)
        if row:
            execute(
                """UPDATE pengaturan_rapor_tahfiz
                   SET tanggal_hijriah=%s, tanggal_masehi=%s, tempat_cetak=%s, nama_kepala=%s, nbm_kepala=%s
                   WHERE id=%s""",
                (*data, row["id"]),
            )
        else:
            execute(
                """INSERT INTO pengaturan_rapor_tahfiz
                   (tampilkan, judul, tanggal_hijriah, tanggal_masehi, tempat_cetak, nama_kepala, nbm_kepala)
                   VALUES (1,'Rapor Tahfiz',%s,%s,%s,%s,%s)""",
                data,
            )
        flash("Pengaturan rapor tahfiz disimpan.", "success")
        return redirect(url_for("main.pengaturan_tahfiz"))
    row = query("SELECT * FROM pengaturan_rapor_tahfiz LIMIT 1", one=True) or {}
    sekolah = query(
        "SELECT tempat_rapor, kabupaten, tanggal_rapor, kepala_sekolah, nip_kepala FROM sekolah ORDER BY id LIMIT 1",
        one=True,
    ) or {}
    tanggal = _teks_tanggal(sekolah.get("tanggal_rapor"))
    tampil = {
        "tanggal_hijriah": row.get("tanggal_hijriah") or "",
        "tanggal_masehi": row.get("tanggal_masehi") or (f"{tanggal} M" if tanggal else ""),
        "tempat_cetak": row.get("tempat_cetak") or sekolah.get("tempat_rapor") or sekolah.get("kabupaten") or "",
        "nama_kepala": row.get("nama_kepala") or sekolah.get("kepala_sekolah") or "",
        "nbm_kepala": row.get("nbm_kepala") or sekolah.get("nip_kepala") or "",
    }
    return render_template("pengaturan_tahfiz.html", row=tampil, nav="pengtahfiz")


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
        aspek=query("SELECT id,nama FROM aspek_tahfiz WHERE aktif=1 ORDER BY urutan, id"),
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
