import io
import re

import xlrd
from openpyxl import load_workbook

from .db import execute, query, transaction


def _text(value):
    if value is None:
        return ""
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value).strip()
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def _jam(value):
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    cleaned = _text(value).replace(",", ".")
    try:
        return int(float(cleaned))
    except ValueError:
        return 0


def _rows_from_xls(data):
    book = xlrd.open_workbook(file_contents=data)
    sheets = []
    for sheet in book.sheets():
        rows = []
        for r in range(sheet.nrows):
            rows.append([sheet.cell_value(r, c) for c in range(sheet.ncols)])
        sheets.append(rows)
    return sheets


def _rows_from_xlsx(data):
    book = load_workbook(io.BytesIO(data), data_only=True)
    sheets = []
    for sheet in book.worksheets:
        rows = []
        for row in sheet.iter_rows(values_only=True):
            rows.append(list(row))
        sheets.append(rows)
    return sheets


def _split_nama(raw):
    text = _text(raw).strip(" ,")
    if "," in text:
        nama, gelar = text.split(",", 1)
        gelar = gelar.strip(" ,")
        if gelar:
            return nama.strip(), gelar
    return text, ""


def _header_col(row, label):
    label = label.upper()
    for index, value in enumerate(row):
        if label in _text(value).upper():
            return index
    return None


def parse_guru_rows(sheets):
    header_at = None
    for rows in sheets:
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                if _text(value).upper() == "NAMA GURU":
                    header_at = (rows, r, c)
                    break
            if header_at:
                break
        if header_at:
            break
    if not header_at:
        raise ValueError("Kolom NAMA GURU tidak ditemukan. Gunakan file jadwal yang sama.")

    rows, header_row, nama_col = header_at
    header = rows[header_row]
    mapel_col = _header_col(header, "MATA PELAJARAN")
    jam_col = _header_col(header, "JUMLAH JAM")
    kelas_col = _header_col(header, "MENGAJAR DI KELAS")
    if mapel_col is None:
        mapel_col = nama_col + 2
    if jam_col is None:
        jam_col = nama_col + 4
    if kelas_col is None:
        kelas_col = nama_col + 5

    teachers = []
    current = None
    for row in rows[header_row + 1 :]:
        def pick(index):
            if index is None or index >= len(row):
                return ""
            return row[index]

        nama = _text(pick(nama_col))
        mapel = _text(pick(mapel_col))
        kelas = _text(pick(kelas_col))
        jam = _jam(pick(jam_col))
        if nama.upper() in {"NAMA KELAS", "NAMA GURU"}:
            break
        if not nama and not mapel:
            continue
        item = {"mapel": mapel, "jam": jam, "kelas": kelas}
        if not nama:
            if current is not None and (mapel or kelas or jam):
                current["items"].append(item)
            continue
        nama_bersih, gelar = _split_nama(nama)
        current = {"nama": nama_bersih, "gelar_belakang": gelar, "items": []}
        if mapel or kelas or jam:
            current["items"].append(item)
        teachers.append(current)

    hasil = []
    for teacher in teachers:
        mapel_parts = []
        kelas_parts = []
        total = 0
        for item in teacher["items"]:
            total += item["jam"]
            if item["mapel"]:
                mapel_parts.append(f"{item['mapel']} ({item['jam']})" if item["jam"] else item["mapel"])
            if item["kelas"] and item["kelas"] not in kelas_parts:
                kelas_parts.append(item["kelas"])
        hasil.append(
            {
                "nama": teacher["nama"],
                "gelar_belakang": teacher["gelar_belakang"],
                "mapel_ajar": ", ".join(mapel_parts),
                "jumlah_jam": total,
                "mengajar_di": "; ".join(kelas_parts),
            }
        )
    if not hasil:
        raise ValueError("Tidak ada nama guru yang terbaca dari file.")
    return hasil


def parse_guru_file(filename, data):
    name = (filename or "").lower()
    if name.endswith(".xlsx"):
        sheets = _rows_from_xlsx(data)
    elif name.endswith(".xls"):
        sheets = _rows_from_xls(data)
    else:
        raise ValueError("File harus berformat .xls atau .xlsx seperti jadwal pelajaran.")
    return parse_guru_rows(sheets)


def ensure_guru_columns():
    cols = {row["Field"] for row in query("SHOW COLUMNS FROM guru")}
    if "mapel_ajar" not in cols:
        execute("ALTER TABLE guru ADD COLUMN mapel_ajar TEXT NULL")
    if "jumlah_jam" not in cols:
        execute("ALTER TABLE guru ADD COLUMN jumlah_jam INT NULL")
    if "mengajar_di" not in cols:
        execute("ALTER TABLE guru ADD COLUMN mengajar_di TEXT NULL")
    execute("ALTER TABLE guru MODIFY jenis_kelamin ENUM('L','P') NULL")
    execute("ALTER TABLE guru MODIFY gelar_belakang VARCHAR(80) DEFAULT ''")


def replace_guru(records):
    ensure_guru_columns()
    existing = query("SELECT id, nama FROM guru")
    by_name = {re.sub(r"\s+", " ", row["nama"]).strip().lower(): row["id"] for row in existing}
    kept = []
    with transaction():
        for rec in records:
            key = rec["nama"].strip().lower()
            if key in by_name:
                guru_id = by_name[key]
                execute(
                    """UPDATE guru
                       SET nama=%s, gelar_belakang=%s, mapel_ajar=%s, jumlah_jam=%s, mengajar_di=%s, aktif=1
                       WHERE id=%s""",
                    (rec["nama"], rec["gelar_belakang"], rec["mapel_ajar"], rec["jumlah_jam"], rec["mengajar_di"], guru_id),
                )
            else:
                guru_id = execute(
                    """INSERT INTO guru
                       (nama, gelar_belakang, mapel_ajar, jumlah_jam, mengajar_di, jenis_kelamin, status_kepegawaian, aktif)
                       VALUES (%s,%s,%s,%s,%s,NULL,'Guru',1)""",
                    (rec["nama"], rec["gelar_belakang"], rec["mapel_ajar"], rec["jumlah_jam"], rec["mengajar_di"]),
                )
                by_name[key] = guru_id
            kept.append(guru_id)
        placeholders = ", ".join(["%s"] * len(kept))
        execute(f"DELETE FROM guru WHERE id NOT IN ({placeholders})", kept)
    return len(kept)
