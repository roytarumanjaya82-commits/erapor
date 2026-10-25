from flask import flash, redirect, session, url_for
from werkzeug.security import generate_password_hash

from .db import execute, query

TUGAS_LABEL = {
    "admin": "Admin Sekolah",
    "bidang_studi": "Guru Bidang Studi",
    "walas": "Wali Kelas",
    "ekskul": "Guru Ekstrakurikuler",
    "tahfidz": "Guru Tahfidz",
    "siswa": "Siswa",
}

# Endpoint lama: siapa yang boleh membukanya.
ENDPOINT_TUGAS = {
    "main.index": {"admin", "bidang_studi", "walas", "ekskul", "tahfidz", "siswa"},
    "main.dashboard": {"admin", "bidang_studi", "walas", "ekskul", "tahfidz", "siswa"},
    "main.perencanaan": {"admin", "bidang_studi"},
    "main.simpan_perencanaan": {"admin", "bidang_studi"},
    "main.data_pelajaran": {"admin", "bidang_studi"},
    "main.form_pelajaran": {"admin"},
    "main.hapus_pelajaran": {"admin"},
    "main.hapus_pelajaran_terpilih": {"admin"},
    "main.data_siswa": {"admin", "walas"},
    "main.form_siswa": {"admin"},
    "main.hapus_siswa": {"admin"},
    "main.hapus_siswa_terpilih": {"admin"},
    "main.data_ekskul": {"admin", "ekskul"},
    "main.form_ekskul": {"admin"},
    "main.hapus_ekskul": {"admin"},
    "main.hapus_ekskul_terpilih": {"admin"},
    "main.peserta_ekskul": {"admin", "ekskul"},
    "main.nilai_tahfiz": {"admin", "tahfidz"},
    "main.simpan_nilai_tahfiz": {"admin", "tahfidz"},
    "main.aspek_tahfiz": {"admin", "tahfidz"},
    "main.form_aspek": {"admin"},
    "main.hapus_aspek": {"admin"},
    "main.hapus_aspek_terpilih": {"admin"},
    "main.mapping_tahfiz": {"admin"},
    "main.form_mapping_tahfiz": {"admin"},
    "main.hapus_mapping_tahfiz": {"admin"},
    "main.hapus_mapping_tahfiz_terpilih": {"admin"},
    "main.pengaturan_tahfiz": {"admin"},
    "main.data_kelompok": {"admin"},
    "main.form_kelompok": {"admin"},
    "main.hapus_kelompok": {"admin"},
    "main.hapus_kelompok_terpilih": {"admin"},
    "main.mapping_rapor": {"admin"},
    "main.form_mapping": {"admin"},
    "main.ubah_mapping": {"admin"},
    "main.hapus_mapping": {"admin"},
    "main.gabung_mapel": {"admin"},
    "main.form_gabung": {"admin"},
    "main.hapus_gabung": {"admin"},
    "main.data_mapel": {"admin"},
    "main.form_mapel": {"admin"},
    "main.hapus_mapel": {"admin"},
    "main.hapus_mapel_terpilih": {"admin"},
    "main.data_guru": {"admin"},
    "main.form_guru": {"admin"},
    "main.form_excel_guru": {"admin"},
    "main.upload_guru": {"admin"},
    "main.hapus_guru": {"admin"},
    "main.data_sekolah": {"admin"},
    "main.form_sekolah": {"admin"},
    "main.hapus_sekolah": {"admin"},
}

_ready = False


def ensure_access():
    global _ready
    if _ready:
        return
    execute(
        """CREATE TABLE IF NOT EXISTS user_tugas (
            user_id INT NOT NULL,
            tugas VARCHAR(30) NOT NULL,
            PRIMARY KEY (user_id, tugas),
            CONSTRAINT fk_ut_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )"""
    )
    execute(
        """CREATE TABLE IF NOT EXISTS dimensi_sikap (
            id INT PRIMARY KEY AUTO_INCREMENT,
            kode VARCHAR(60) NULL,
            nama VARCHAR(150) NOT NULL,
            indikator TEXT,
            kelas_7 TINYINT DEFAULT 1,
            kelas_8 TINYINT DEFAULT 1,
            kelas_9 TINYINT DEFAULT 1,
            urutan INT DEFAULT 0,
            UNIQUE KEY uk_dimensi_kode (kode)
        )"""
    )
    execute(
        """CREATE TABLE IF NOT EXISTS predikat_sikap (
            id INT PRIMARY KEY AUTO_INCREMENT,
            nama VARCHAR(50) NOT NULL,
            deskripsi VARCHAR(255),
            aktif TINYINT DEFAULT 1,
            urutan INT DEFAULT 0
        )"""
    )
    execute(
        """CREATE TABLE IF NOT EXISTS nilai_ekskul (
            id INT PRIMARY KEY AUTO_INCREMENT,
            ekskul_id INT NOT NULL,
            siswa_id INT NOT NULL,
            nilai VARCHAR(30),
            UNIQUE KEY uk_nilai_ekskul (ekskul_id, siswa_id)
        )"""
    )
    try:
        execute("ALTER TABLE users MODIFY role ENUM('admin','guru','wali_kelas','siswa') NOT NULL DEFAULT 'guru'")
    except Exception:
        pass
    kolom = {row["Field"] for row in query("SHOW COLUMNS FROM users")}
    tambahan = {
        "email": "ALTER TABLE users ADD COLUMN email VARCHAR(150) NULL",
        "aktif": "ALTER TABLE users ADD COLUMN aktif TINYINT NOT NULL DEFAULT 1",
        "login_terakhir": "ALTER TABLE users ADD COLUMN login_terakhir DATETIME NULL",
        "ip_address": "ALTER TABLE users ADD COLUMN ip_address VARCHAR(45) NULL",
        "sedang_login": "ALTER TABLE users ADD COLUMN sedang_login TINYINT NOT NULL DEFAULT 0",
    }
    for nama, sql in tambahan.items():
        if nama not in kolom:
            execute(sql)
    kolom_sekolah = {row["Field"] for row in query("SHOW COLUMNS FROM sekolah")}
    tambahan_sekolah = {
        "status_sekolah": "ALTER TABLE sekolah ADD COLUMN status_sekolah VARCHAR(30) NULL",
        "tempat_rapor": "ALTER TABLE sekolah ADD COLUMN tempat_rapor VARCHAR(100) NULL",
        "tanggal_rapor": "ALTER TABLE sekolah ADD COLUMN tanggal_rapor DATE NULL",
    }
    for nama, sql in tambahan_sekolah.items():
        if nama not in kolom_sekolah:
            execute(sql)
    kolom_siswa = {row["Field"] for row in query("SHOW COLUMNS FROM siswa")}
    if "nik" not in kolom_siswa:
        execute("ALTER TABLE siswa ADD COLUMN nik VARCHAR(20) NULL")
    try:
        execute("ALTER TABLE siswa MODIFY jenis_kelamin ENUM('L','P') NULL")
    except Exception:
        pass
    kolom_pelajaran = {row["Field"] for row in query("SHOW COLUMNS FROM pelajaran")}
    if "kode" not in kolom_pelajaran:
        execute("ALTER TABLE pelajaran ADD COLUMN kode VARCHAR(36) NULL")
    if "status_kurikulum" not in kolom_pelajaran:
        execute("ALTER TABLE pelajaran ADD COLUMN status_kurikulum VARCHAR(30) NULL")
    try:
        execute("ALTER TABLE pelajaran MODIFY guru_id INT NULL")
        execute("ALTER TABLE pelajaran MODIFY jam_per_minggu INT NULL")
    except Exception:
        pass
    execute("UPDATE pelajaran SET kode=LOWER(UUID()) WHERE kode IS NULL OR kode=''")
    try:
        execute("ALTER TABLE kelompok_mapel MODIFY kode VARCHAR(60) NOT NULL")
    except Exception:
        pass
    execute(
        "UPDATE kelompok_mapel SET nama=%s WHERE kode='C' AND nama=%s",
        ("Kelompok C (Pilihan / Peminatan)", "Kelompok C (Peminatan)"),
    )
    execute(
        "UPDATE kelompok_mapel SET kode=%s WHERE kode='M' AND nama='Muatan Lokal'",
        ("Muatan Lokal",),
    )
    kolom_ekskul = {row["Field"] for row in query("SHOW COLUMNS FROM ekstrakurikuler")}
    if "nama_pembina" not in kolom_ekskul:
        execute("ALTER TABLE ekstrakurikuler ADD COLUMN nama_pembina VARCHAR(150) NULL")
    execute(
        """UPDATE ekstrakurikuler e
           JOIN guru g ON g.id=e.pembina_id
           SET e.nama_pembina=TRIM(CONCAT(
             IF(g.gelar_depan IS NULL OR g.gelar_depan='', '', CONCAT(g.gelar_depan, ' ')),
             g.nama,
             IF(g.gelar_belakang IS NULL OR g.gelar_belakang='', '', CONCAT(', ', g.gelar_belakang))
           ))
           WHERE e.nama_pembina IS NULL OR e.nama_pembina=''"""
    )
    execute(
        """CREATE TABLE IF NOT EXISTS peserta_ekskul (
            id INT PRIMARY KEY AUTO_INCREMENT,
            ekskul_id INT NOT NULL,
            siswa_id INT NOT NULL,
            UNIQUE KEY uk_peserta_ekskul (ekskul_id, siswa_id),
            CONSTRAINT fk_peserta_ekskul FOREIGN KEY (ekskul_id) REFERENCES ekstrakurikuler(id) ON DELETE CASCADE,
            CONSTRAINT fk_peserta_siswa FOREIGN KEY (siswa_id) REFERENCES siswa(id) ON DELETE CASCADE
        )"""
    )
    kolom_mapping = {row["Field"] for row in query("SHOW COLUMNS FROM mapping_rapor")}
    tambahan_mapping = {
        "kurikulum": "ALTER TABLE mapping_rapor ADD COLUMN kurikulum VARCHAR(80) NULL",
        "tingkat": "ALTER TABLE mapping_rapor ADD COLUMN tingkat VARCHAR(10) NULL",
        "nama_lokal": "ALTER TABLE mapping_rapor ADD COLUMN nama_lokal VARCHAR(150) NULL",
        "kelompok_id": "ALTER TABLE mapping_rapor ADD COLUMN kelompok_id INT NULL",
    }
    for nama, sql in tambahan_mapping.items():
        if nama not in kolom_mapping:
            execute(sql)
    execute(
        """UPDATE mapping_rapor mr
           JOIN mata_pelajaran m ON m.id=mr.mapel_id
           SET mr.nama_lokal=m.nama
           WHERE mr.nama_lokal IS NULL OR mr.nama_lokal=''"""
    )
    execute(
        """UPDATE mapping_rapor mr
           JOIN mata_pelajaran m ON m.id=mr.mapel_id
           SET mr.kelompok_id=m.kelompok_id
           WHERE mr.kelompok_id IS NULL"""
    )
    execute(
        "UPDATE mapping_rapor SET kurikulum='Kurikulum Merdeka' WHERE kurikulum IS NULL OR kurikulum=''"
    )
    tanpa_tingkat = query(
        "SELECT id, mapel_id, tampil_rapor, urutan, kurikulum, nama_lokal, kelompok_id FROM mapping_rapor WHERE tingkat IS NULL OR tingkat=''"
    )
    for baris in tanpa_tingkat:
        execute("UPDATE mapping_rapor SET tingkat='7' WHERE id=%s", (baris["id"],))
        for tingkat in ("8", "9"):
            ada = query(
                "SELECT id FROM mapping_rapor WHERE mapel_id=%s AND tingkat=%s AND kurikulum=%s",
                (baris["mapel_id"], tingkat, baris["kurikulum"]),
                one=True,
            )
            if ada:
                continue
            execute(
                """INSERT INTO mapping_rapor
                   (mapel_id, tampil_rapor, urutan, kurikulum, tingkat, nama_lokal, kelompok_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    baris["mapel_id"],
                    baris["tampil_rapor"],
                    baris["urutan"],
                    baris["kurikulum"],
                    tingkat,
                    baris["nama_lokal"],
                    baris["kelompok_id"],
                ),
            )
    indeks_mapping = {row["Key_name"] for row in query("SHOW INDEX FROM mapping_rapor")}
    if "uk_mapping_rapor" not in indeks_mapping:
        try:
            execute(
                "ALTER TABLE mapping_rapor ADD UNIQUE KEY uk_mapping_rapor (kurikulum, tingkat, mapel_id)"
            )
        except Exception:
            pass
    indeks = {row["Key_name"] for row in query("SHOW INDEX FROM pelajaran")}
    if "uk_pelajaran_kode" not in indeks:
        try:
            execute("ALTER TABLE pelajaran ADD UNIQUE KEY uk_pelajaran_kode (kode)")
        except Exception:
            pass
    kolom_dimensi = {row["Field"] for row in query("SHOW COLUMNS FROM dimensi_sikap")}
    if "kode" not in kolom_dimensi:
        execute("ALTER TABLE dimensi_sikap ADD COLUMN kode VARCHAR(60) NULL")
    if not query("SELECT id FROM dimensi_sikap LIMIT 1", one=True):
        for i, (nama, indikator) in enumerate(
            [
                ("Keimanan dan ketakwaan kepada Tuhan YME", "Berdoa, menjalankan ibadah, menghormati keyakinan, berakhlak baik"),
                ("Penalaran kritis", "Bertanya dengan baik, mempertimbangkan informasi sebelum bertindak"),
                ("Kreativitas", "Memiliki inisiatif, mencoba cara baru, menghasilkan gagasan positif"),
                ("Gotong royong", "Mau bekerja sama, berbagi tugas, dan membantu teman"),
            ],
            start=1,
        ):
            execute(
                "INSERT INTO dimensi_sikap (nama, indikator, urutan) VALUES (%s,%s,%s)",
                (nama, indikator, i),
            )
    _isi_kode_dimensi()
    indeks_dimensi = {row["Key_name"] for row in query("SHOW INDEX FROM dimensi_sikap")}
    if "uk_dimensi_kode" not in indeks_dimensi:
        try:
            execute("ALTER TABLE dimensi_sikap ADD UNIQUE KEY uk_dimensi_kode (kode)")
        except Exception:
            pass
    if not query("SELECT id FROM predikat_sikap LIMIT 1", one=True):
        for i, (nama, deskripsi) in enumerate(
            [
                ("Berkembang", "Menunjukkan perkembangan pada dimensi"),
                ("Cakap", "Menunjukkan kemampuan yang cakap pada dimensi"),
                ("Mahir", "Menunjukkan penguasaan yang mahir pada dimensi"),
            ],
            start=1,
        ):
            execute(
                "INSERT INTO predikat_sikap (nama, deskripsi, urutan) VALUES (%s,%s,%s)",
                (nama, deskripsi, i),
            )
    _siapkan_aspek()
    _siapkan_mapping_tahfiz()
    _siapkan_pengaturan_tahfiz()
    _seed_demo_users()
    _ready = True


def _siapkan_pengaturan_tahfiz():
    kolom = {row["Field"] for row in query("SHOW COLUMNS FROM pengaturan_rapor_tahfiz")}
    tambah = {
        "tanggal_hijriah": "VARCHAR(80) NULL",
        "tanggal_masehi": "VARCHAR(80) NULL",
        "tempat_cetak": "VARCHAR(120) NULL",
        "nama_kepala": "VARCHAR(150) NULL",
        "nbm_kepala": "VARCHAR(40) NULL",
    }
    for nama, tipe in tambah.items():
        if nama not in kolom:
            execute(f"ALTER TABLE pengaturan_rapor_tahfiz ADD COLUMN {nama} {tipe}")


def _siapkan_mapping_tahfiz():
    kolom = {row["Field"] for row in query("SHOW COLUMNS FROM mapping_guru_tahfiz")}
    if "dibuat" not in kolom:
        execute("ALTER TABLE mapping_guru_tahfiz ADD COLUMN dibuat DATETIME NULL")
    execute("UPDATE mapping_guru_tahfiz SET dibuat=NOW() WHERE dibuat IS NULL")


def _siapkan_aspek():
    kolom = {row["Field"] for row in query("SHOW COLUMNS FROM aspek_tahfiz")}
    if "urutan" not in kolom:
        execute("ALTER TABLE aspek_tahfiz ADD COLUMN urutan INT NULL")
    if "aktif" not in kolom:
        execute("ALTER TABLE aspek_tahfiz ADD COLUMN aktif TINYINT NOT NULL DEFAULT 1")
    if "dibuat" not in kolom:
        execute("ALTER TABLE aspek_tahfiz ADD COLUMN dibuat DATETIME NULL")
    baris = query("SELECT id, urutan FROM aspek_tahfiz ORDER BY id")
    for nomor, row in enumerate(baris, start=1):
        if row["urutan"] is None:
            execute("UPDATE aspek_tahfiz SET urutan=%s WHERE id=%s", (nomor, row["id"]))
    execute("UPDATE aspek_tahfiz SET aktif=1 WHERE aktif IS NULL")
    execute("UPDATE aspek_tahfiz SET dibuat=NOW() WHERE dibuat IS NULL")


def _isi_kode_dimensi():
    baris = query("SELECT id, nama, kode FROM dimensi_sikap ORDER BY id")
    terpakai = {row["kode"] for row in baris if row.get("kode")}
    for row in baris:
        if row.get("kode"):
            continue
        dasar = []
        for ch in (row["nama"] or "").lower():
            if ch.isalnum():
                dasar.append(ch)
            elif dasar and dasar[-1] != "-":
                dasar.append("-")
        kode = "".join(dasar).strip("-").split("-")[0][:40] or "dimensi"
        calon = kode
        n = 2
        while calon in terpakai:
            calon = f"{kode}{n}"
            n += 1
        terpakai.add(calon)
        execute("UPDATE dimensi_sikap SET kode=%s WHERE id=%s AND (kode IS NULL OR kode='')", (calon, row["id"]))


def _guru_id(nama):
    row = query("SELECT id FROM guru WHERE nama=%s", (nama,), one=True)
    return row["id"] if row else None


def _seed_user(username, nama, guru_nama, tugas_list):
    if query("SELECT id FROM users WHERE username=%s", (username,), one=True):
        return
    gid = _guru_id(guru_nama)
    uid = execute(
        "INSERT INTO users (username, password_hash, nama, role, guru_id) VALUES (%s,%s,%s,'guru',%s)",
        (username, generate_password_hash("guru123"), nama, gid),
    )
    for tugas in tugas_list:
        execute("INSERT INTO user_tugas (user_id, tugas) VALUES (%s,%s)", (uid, tugas))


def _seed_demo_users():
    _seed_user("roy.tarumanjaya", "Roy Tarumanjaya, S.Kom.", "Roy Tarumanjaya", ["bidang_studi"])
    _seed_user("yunus.anis", "Yunus Anis, M.Pd.", "Yunus Anis", ["walas", "bidang_studi"])
    _seed_user("ilham", "Ilham", "Ilham", ["ekskul"])
    _seed_user("agus.salim", "Agus Salim, M.Pd.", "Agus Salim", ["tahfidz"])


def tugas_for(user_id, role, guru_id):
    if role == "admin":
        return {"admin"}
    found = {row["tugas"] for row in query("SELECT tugas FROM user_tugas WHERE user_id=%s", (user_id,))}
    if role == "siswa":
        found.add("siswa")
    if guru_id:
        if query("SELECT COUNT(*) AS n FROM pelajaran WHERE guru_id=%s", (guru_id,), one=True)["n"]:
            found.add("bidang_studi")
        if query("SELECT COUNT(*) AS n FROM kelas WHERE wali_kelas_id=%s", (guru_id,), one=True)["n"]:
            found.add("walas")
        if query("SELECT COUNT(*) AS n FROM ekstrakurikuler WHERE pembina_id=%s", (guru_id,), one=True)["n"]:
            found.add("ekskul")
        if query("SELECT COUNT(*) AS n FROM mapping_guru_tahfiz WHERE guru_id=%s", (guru_id,), one=True)["n"]:
            found.add("tahfidz")
    return found


def load_tugas():
    if not session.get("user_id"):
        return set()
    try:
        ensure_access()
        user = query("SELECT id, role, guru_id FROM users WHERE id=%s", (session["user_id"],), one=True)
    except Exception:
        return set(session.get("tugas") or [])
    if not user:
        return set()
    tugas = tugas_for(user["id"], user["role"], user["guru_id"])
    session["tugas"] = sorted(tugas)
    session["guru_id"] = user["guru_id"]
    session["role"] = user["role"]
    return tugas


def allowed(endpoint, tugas):
    if "admin" in tugas:
        return True
    needed = ENDPOINT_TUGAS.get(endpoint)
    if needed is None:
        return False
    return bool(tugas.intersection(needed))


def guard_request():
    from flask import request

    endpoint = request.endpoint or ""
    if endpoint in {"auth.login", "auth.logout", "main.publik", "menu.publik", "static"} or endpoint.startswith("static"):
        return None
    if not session.get("user_id"):
        return None
    if endpoint in {"main.dashboard", "main.index"}:
        load_tugas()
        return None
    tugas = load_tugas()
    if not allowed(endpoint, tugas):
        flash("Menu ini tidak termasuk tugas Anda.", "error")
        return redirect(url_for("main.dashboard"))
    return None
