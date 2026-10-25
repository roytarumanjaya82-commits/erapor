# eRapor SMPM22SETIABUDIPAMULANG

Aplikasi rapor digital untuk **SMP Muhammadiyah 22 Setiabudi Pamulang**, dibuat dengan **Python (Flask)** dan **MySQL**.

## Fitur

- Dasbor admin (rombel, siswa, guru, pembelajaran, progres penilaian)
- Data referensi: sekolah, guru, kelas, siswa, pelajaran, mapel, kelompok mapel, gabung mapel, mapping rapor, ekskul, tryout
- Perencanaan penilaian (KKM / mapping)
- Modul rapor tahfiz (aspek, mapping guru, pengaturan, input nilai)

## Persyaratan

- Python 3.10+
- MySQL 8 (user `root`, password kosong sesuai `.env`)

## Instalasi

```powershell
cd d:\RAPORT
python -m pip install -r requirements.txt
python seed.py
python run.py
```

Buka [http://127.0.0.1:5000](http://127.0.0.1:5000)

**Login default:** `admin` / `admin123`

Skrip `seed.py` membuat database `erapor_smamduma` beserta data contoh (24 rombel, 791 siswa, 44 guru, 408 pembelajaran).
