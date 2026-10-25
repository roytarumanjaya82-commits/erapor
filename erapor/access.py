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
    "main.data_siswa": {"admin", "walas"},
    "main.form_siswa": {"admin"},
    "main.hapus_siswa": {"admin"},
    "main.data_ekskul": {"admin", "ekskul"},
    "main.hapus_ekskul": {"admin"},
    "main.nilai_tahfiz": {"admin", "tahfidz"},
    "main.simpan_nilai_tahfiz": {"admin", "tahfidz"},
    "main.aspek_tahfiz": {"admin", "tahfidz"},
    "main.hapus_aspek": {"admin"},
    "main.mapping_tahfiz": {"admin"},
    "main.hapus_mapping_tahfiz": {"admin"},
    "main.pengaturan_tahfiz": {"admin"},
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
            nama VARCHAR(150) NOT NULL,
            indikator TEXT,
            kelas_7 TINYINT DEFAULT 1,
            kelas_8 TINYINT DEFAULT 1,
            kelas_9 TINYINT DEFAULT 1,
            urutan INT DEFAULT 0
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
    _seed_demo_users()
    _ready = True


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
    if endpoint in {"auth.login", "auth.logout", "main.publik", "static"} or endpoint.startswith("static"):
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
