"""Isi database eRapor SMPM22SETIABUDIPAMULANG (SMP Muhammadiyah 22 Setiabudi Pamulang)."""
import os
import random
from datetime import date

import pymysql
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

random.seed(25)

NAMA_L = [
    "Ahmad", "Muhammad", "Fajar", "Rizki", "Dimas", "Andi", "Budi", "Hendra",
    "Ilham", "Yoga", "Rafi", "Fauzan", "Aditya", "Bayu", "Dedi", "Eko", "Farhan",
    "Gilang", "Hasan", "Irfan", "Joko", "Kurniawan", "Lukman", "Naufal", "Omar",
    "Prasetyo", "Qori", "Reza", "Satria", "Taufik", "Umar", "Wahyu", "Yusuf", "Zaki",
]
NAMA_P = [
    "Aisyah", "Siti", "Nur", "Dewi", "Putri", "Anisa", "Fitri", "Hana", "Intan",
    "Laila", "Maya", "Nadia", "Rina", "Salma", "Tina", "Wulan", "Zahra", "Aulia",
    "Bunga", "Citra", "Dina", "Elisa", "Farah", "Gita", "Hesti", "Indah", "Jihan",
    "Kartika", "Lestari", "Mira", "Nisa", "Olivia", "Puspita", "Qonita", "Rani",
]
BELAKANG = [
    "Pratama", "Saputra", "Wijaya", "Hidayat", "Ramadhan", "Santoso", "Nugroho",
    "Kusuma", "Mahendra", "Syahputra", "Fauzi", "Rahman", "Hakim", "Maulana",
    "Permata", "Sari", "Lestari", "Wulandari", "Anggraini", "Safitri", "Azzahra",
    "Kurnia", "Utami", "Purnama", "Gunawan",
]
KOTA = ["Jakarta", "Tangerang", "Depok", "Bogor", "Bekasi", "Pamulang", "Ciputat", "Serang"]


def nama_orang(jk):
    first = random.choice(NAMA_L if jk == "L" else NAMA_P)
    last = random.choice(BELAKANG)
    mid = random.choice(NAMA_L + NAMA_P) if random.random() < 0.35 else ""
    return " ".join(p for p in (first, mid, last) if p)


def connect(db=None):
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=db,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def run_schema(cur, path):
    sql = open(path, encoding="utf-8").read()
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    conn = connect()
    cur = conn.cursor()
    run_schema(cur, os.path.join(root, "schema.sql"))
    conn.select_db(os.getenv("MYSQL_DATABASE", "erapor_smamduma"))
    cur = conn.cursor()

    cur.execute(
        """INSERT INTO sekolah (nama,npsn,jenjang,alamat,kelurahan,kecamatan,kabupaten,provinsi,
           kode_pos,telepon,email,website,kepala_sekolah,nip_kepala)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            "SMP Muhammadiyah 22 Setiabudi Pamulang",
            "20603175",
            "SMP",
            "Jl. Setiabudi",
            "Setiabudi",
            "Pamulang",
            "Kota Tangerang Selatan",
            "Banten",
            "15417",
            "021-7410000",
            "info@smpm22setiabudipamulang.sch.id",
            "https://akademik.smpm22setiabudipamulang.sch.id",
            "Drs. H. Ahmad Fauzi, M.Pd.",
            "196508121990031012",
        ),
    )
    cur.execute("INSERT INTO tahun_ajaran (tahun, semester, aktif) VALUES (%s,%s,1)", ("2026/2027", 1))
    ta_id = cur.lastrowid

    guru_ids = []
    for i in range(44):
        jk = "L" if i % 3 != 1 else "P"
        nama = nama_orang(jk)
        gelar_b = random.choice(["S.Pd.", "S.Pd., M.Pd.", "S.Ag.", "S.Si.", "S.E.", "M.Pd."])
        cur.execute(
            """INSERT INTO guru (nip,nuptk,nama,gelar_belakang,jenis_kelamin,tempat_lahir,
               tanggal_lahir,agama,alamat,no_hp,email,status_kepegawaian,aktif)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)""",
            (
                f"197{random.randint(0,9)}{random.randint(10,12):02d}{random.randint(10,28):02d}{1990+i%15}{i%2+1:02d}{1000+i}",
                f"1{random.randint(10**15, 10**16-1)}",
                nama,
                gelar_b,
                jk,
                random.choice(KOTA),
                date(1975 + i % 20, (i % 12) + 1, (i % 27) + 1),
                "Islam",
                f"Pamulang, Tangerang Selatan",
                f"08{random.randint(11,21)}{random.randint(10000000,99999999)}",
                f"guru{i+1:02d}@smpm22setiabudipamulang.sch.id",
                "Guru Tetap" if i < 38 else "Guru Honorer",
            ),
        )
        guru_ids.append(cur.lastrowid)

    cur.execute(
        "INSERT INTO users (username,password_hash,nama,role) VALUES (%s,%s,%s,'admin')",
        ("admin", generate_password_hash("admin123"), "Administrator"),
    )

    tingkat_list = [("X", 8), ("XI", 8), ("XII", 8)]
    kelas_ids = []
    n = 0
    for tingkat, jumlah in tingkat_list:
        for i in range(1, jumlah + 1):
            wali = guru_ids[n % len(guru_ids)]
            nama = f"{tingkat}-{i}"
            cur.execute(
                "INSERT INTO kelas (nama,tingkat,jurusan,wali_kelas_id,tahun_ajaran_id,kapasitas) VALUES (%s,%s,%s,%s,%s,%s)",
                (nama, tingkat, "Umum", wali, ta_id, 36),
            )
            kelas_ids.append(cur.lastrowid)
            n += 1

    # 791 siswa: sebar merata ke 24 kelas (~33)
    total_siswa = 791
    base = total_siswa // 24
    sisa = total_siswa % 24
    nis_counter = 2024001
    for idx, kid in enumerate(kelas_ids):
        jumlah = base + (1 if idx < sisa else 0)
        for j in range(jumlah):
            jk = "L" if (idx + j) % 2 == 0 else "P"
            cur.execute(
                """INSERT INTO siswa (nis,nisn,nama,jenis_kelamin,tempat_lahir,tanggal_lahir,
                   agama,alamat,nama_ayah,nama_ibu,no_hp,kelas_id,status)
                   VALUES (%s,%s,%s,%s,%s,%s,'Islam',%s,%s,%s,%s,%s,'aktif')""",
                (
                    str(nis_counter),
                    f"00{random.randint(10**8, 10**9-1)}",
                    nama_orang(jk),
                    jk,
                    random.choice(KOTA),
                    date(2008 + (idx // 8), (j % 12) + 1, (j % 27) + 1),
                    "Pamulang",
                    nama_orang("L"),
                    nama_orang("P"),
                    f"08{random.randint(11,21)}{random.randint(10000000,99999999)}",
                    kid,
                ),
            )
            nis_counter += 1

    kelompok = [
        ("A", "Kelompok A (Umum)", 1),
        ("B", "Kelompok B (Umum)", 2),
        ("C", "Kelompok C (Peminatan)", 3),
        ("M", "Muatan Lokal", 4),
    ]
    kel_ids = {}
    for kode, nama, ur in kelompok:
        cur.execute("INSERT INTO kelompok_mapel (kode,nama,urutan) VALUES (%s,%s,%s)", (kode, nama, ur))
        kel_ids[kode] = cur.lastrowid

    mapel_def = [
        ("PAI", "Pendidikan Agama Islam", "A", 75),
        ("PPKN", "Pendidikan Pancasila", "A", 75),
        ("BIN", "Bahasa Indonesia", "A", 75),
        ("MTK", "Matematika", "A", 75),
        ("SEJ", "Sejarah", "A", 75),
        ("BIG", "Bahasa Inggris", "A", 75),
        ("PJOK", "Pendidikan Jasmani", "B", 75),
        ("SBD", "Seni Budaya", "B", 75),
        ("PKWU", "Prakarya dan Kewirausahaan", "B", 75),
        ("INF", "Informatika", "B", 75),
        ("FIS", "Fisika", "C", 75),
        ("KIM", "Kimia", "C", 75),
        ("BIO", "Biologi", "C", 75),
        ("GEO", "Geografi", "C", 75),
        ("EKO", "Ekonomi", "C", 75),
        ("SOS", "Sosiologi", "C", 75),
        ("BAR", "Bahasa Arab", "M", 75),
    ]
    mapel_ids = []
    for kode, nama, kel, kkm in mapel_def:
        cur.execute(
            "INSERT INTO mata_pelajaran (kode,nama,kelompok_id,kkm_default) VALUES (%s,%s,%s,%s)",
            (kode, nama, kel_ids[kel], kkm),
        )
        mapel_ids.append(cur.lastrowid)

    pelajaran_ids = []
    gi = 0
    for kid in kelas_ids:
        for mid in mapel_ids:
            gid = guru_ids[gi % len(guru_ids)]
            cur.execute(
                "INSERT INTO pelajaran (tahun_ajaran_id,kelas_id,mapel_id,guru_id,jam_per_minggu) VALUES (%s,%s,%s,%s,%s)",
                (ta_id, kid, mid, gid, 2 + (gi % 3)),
            )
            pelajaran_ids.append(cur.lastrowid)
            gi += 1

    # 330 dari 408 ter-mapping rencana
    mapped_set = set(random.sample(pelajaran_ids, 330))
    for pid in pelajaran_ids:
        cur.execute(
            "INSERT INTO perencanaan_penilaian (pelajaran_id,jumlah_tp,kkm,mapped) VALUES (%s,%s,75,%s)",
            (pid, random.choice([3, 4, 5, 6]), 1 if pid in mapped_set else 0),
        )

    cur.execute(
        """SELECT pel.id AS pelajaran_id, s.id AS siswa_id
           FROM pelajaran pel
           JOIN siswa s ON s.kelas_id=pel.kelas_id AND s.status='aktif'"""
    )
    pasangan = cur.fetchall()
    total_entri = len(pasangan)
    n_f = int(round(total_entri * 0.82))
    n_s = int(round(total_entri * 0.81))
    idx = list(range(total_entri))
    random.shuffle(idx)
    f_rows = [
        (pasangan[i]["pelajaran_id"], pasangan[i]["siswa_id"], round(random.uniform(65, 98), 2))
        for i in idx[:n_f]
    ]
    s_rows = [
        (pasangan[i]["pelajaran_id"], pasangan[i]["siswa_id"], round(random.uniform(60, 97), 2))
        for i in idx[:n_s]
    ]
    cur.executemany(
        "INSERT INTO nilai_formatif (pelajaran_id,siswa_id,nilai) VALUES (%s,%s,%s)", f_rows
    )
    cur.executemany(
        "INSERT INTO nilai_sumatif (pelajaran_id,siswa_id,nilai) VALUES (%s,%s,%s)", s_rows
    )

    ekskul = [
        "Pramuka", "Paskibra", "PMR", "Rohis", "Futsal", "Basket", "Voli",
        "Paduan Suara", "Jurnalistik", "KIR", "Tahfiz", "English Club",
    ]
    for i, nama in enumerate(ekskul):
        cur.execute(
            "INSERT INTO ekstrakurikuler (nama, pembina_id) VALUES (%s,%s)",
            (nama, guru_ids[i % len(guru_ids)]),
        )

    for i, mid in enumerate(mapel_ids, start=1):
        cur.execute(
            "INSERT INTO mapping_rapor (mapel_id, tampil_rapor, urutan) VALUES (%s,1,%s)",
            (mid, i),
        )

    cur.execute("INSERT INTO gabung_mapel (nama_gabungan) VALUES (%s)", ("Ilmu Pengetahuan Alam",))
    gid = cur.lastrowid
    for kode in ("FIS", "KIM", "BIO"):
        mid = mapel_ids[[m[0] for m in mapel_def].index(kode)]
        cur.execute("INSERT INTO gabung_mapel_item (gabung_id, mapel_id) VALUES (%s,%s)", (gid, mid))

    cur.execute(
        "INSERT INTO tryout (nama, tanggal, tingkat) VALUES (%s,%s,'XII')",
        ("Tryout UTBK Gelombang 1", date(2026, 10, 12)),
    )
    cur.execute(
        "INSERT INTO tryout (nama, tanggal, tingkat) VALUES (%s,%s,'XII')",
        ("Tryout UTBK Gelombang 2", date(2026, 11, 16)),
    )

    aspek = [
        ("Hafalan Juz 30", "Hafalan", 75),
        ("Tajwid", "Tilawah", 75),
        ("Kelancaran", "Tilawah", 75),
        ("Adab Tilawah", "Sikap", 80),
    ]
    aspek_ids = []
    for nama, jenis, kkm in aspek:
        cur.execute("INSERT INTO aspek_tahfiz (nama,jenis,kkm) VALUES (%s,%s,%s)", (nama, jenis, kkm))
        aspek_ids.append(cur.lastrowid)

    tahfiz_guru = guru_ids[:8]
    for i, kid in enumerate(kelas_ids):
        cur.execute(
            "INSERT INTO mapping_guru_tahfiz (guru_id,kelas_id,aspek_id) VALUES (%s,%s,%s)",
            (tahfiz_guru[i % len(tahfiz_guru)], kid, aspek_ids[0]),
        )

    cur.execute(
        "INSERT INTO pengaturan_rapor_tahfiz (tampilkan,judul,keterangan) VALUES (1,%s,%s)",
        ("Rapor Tahfiz SMPM22SETIABUDIPAMULANG", "Nilai tahfiz ditampilkan pada rapor semester."),
    )

    print("Seed selesai.")
    print("Login: admin / admin123")
    cur.execute("SELECT COUNT(*) n FROM kelas")
    print("Kelas:", cur.fetchone()["n"])
    cur.execute("SELECT COUNT(*) n FROM siswa")
    print("Siswa:", cur.fetchone()["n"])
    cur.execute("SELECT COUNT(*) n FROM guru")
    print("Guru:", cur.fetchone()["n"])
    cur.execute("SELECT COUNT(*) n FROM pelajaran")
    print("Pelajaran:", cur.fetchone()["n"])
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
