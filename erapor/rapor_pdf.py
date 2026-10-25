import os
from io import BytesIO

from fpdf import FPDF

LEBAR = (12, 70, 16, 22, 22, 22, 22)


def _font(pdf):
    regular = r"C:\Windows\Fonts\arial.ttf"
    tebal = r"C:\Windows\Fonts\arialbd.ttf"
    if os.path.exists(regular) and os.path.exists(tebal):
        pdf.add_font("Raport", "", regular)
        pdf.add_font("Raport", "B", tebal)
        return "Raport"
    return "Helvetica"


def _angka(nilai):
    if nilai is None or nilai == "":
        return "-"
    angka = float(nilai)
    if angka == int(angka):
        return str(int(angka))
    return f"{angka:.2f}".rstrip("0").rstrip(".")


def _baris(pdf, isi, tinggi=7, tebal=False):
    pdf.set_font(pdf.font_rapor, "B" if tebal else "", 8)
    x = pdf.l_margin
    y = pdf.get_y()
    for lebar, teks, align in zip(LEBAR, isi, ("C", "L", "C", "C", "C", "C", "C")):
        pdf.set_xy(x, y)
        pdf.cell(lebar, tinggi, str(teks), border=1, align=align)
        x += lebar
    pdf.set_xy(pdf.l_margin, y + tinggi)


def _kepala_tabel(pdf):
    pdf.set_font(pdf.font_rapor, "B", 8)
    pdf.set_fill_color(245, 245, 245)
    y = pdf.get_y()
    x = pdf.l_margin
    tinggi = 6
    span = (
        (0, "No"),
        (1, "Mata Pelajaran"),
        (2, "KKM"),
    )
    for indeks, judul in span:
        pdf.rect(x, y, LEBAR[indeks], tinggi * 2, style="DF")
        pdf.set_xy(x, y + 3)
        pdf.cell(LEBAR[indeks], tinggi, judul, align="C")
        x += LEBAR[indeks]
    pdf.rect(x, y, LEBAR[3] + LEBAR[4], tinggi, style="DF")
    pdf.set_xy(x, y)
    pdf.cell(LEBAR[3] + LEBAR[4], tinggi, "Asesmen Formatif", align="C")
    pdf.rect(x + LEBAR[3] + LEBAR[4], y, LEBAR[5] + LEBAR[6], tinggi, style="DF")
    pdf.set_xy(x + LEBAR[3] + LEBAR[4], y)
    pdf.cell(LEBAR[5] + LEBAR[6], tinggi, "Asesmen Sumatif", align="C")
    pdf.set_xy(x, y + tinggi)
    for indeks, judul in ((3, "Formatif 1"), (4, "Formatif 2"), (5, "Sumatif"), (6, "ASTS")):
        pdf.cell(LEBAR[indeks], tinggi, judul, border=1, align="C", fill=True)
    pdf.set_xy(pdf.l_margin, y + tinggi * 2)


def _baris_nilai(pdf, teks, lebar):
    pdf.set_font(pdf.font_rapor, "", 9)
    kata = str(teks or "-").split() or ["-"]
    baris = []
    sekarang = ""
    for bagian in kata:
        calon = (sekarang + " " + bagian).strip()
        awalan = ": " if not baris else "  "
        if pdf.get_string_width(awalan + calon) <= lebar:
            sekarang = calon
        else:
            if sekarang:
                baris.append(sekarang)
            sekarang = bagian
    if sekarang:
        baris.append(sekarang)
    return baris or ["-"]


def _pasangan(pdf, kiri, kanan):
    """Dua kolom identitas. Nilai yang panjang turun baris di kolomnya sendiri."""
    pdf.set_font(pdf.font_rapor, "", 9)
    label_kiri, nilai_kiri = 34, 70
    label_kanan, nilai_kanan = 32, 50
    kiri_baris = _baris_nilai(pdf, kiri[1], nilai_kiri)
    kanan_baris = _baris_nilai(pdf, kanan[1], nilai_kanan)
    tinggi = 5
    jumlah = max(len(kiri_baris), len(kanan_baris))
    y = pdf.get_y()
    x0 = pdf.l_margin
    pdf.set_xy(x0, y)
    pdf.cell(label_kiri, tinggi, kiri[0])
    for indeks, teks in enumerate(kiri_baris):
        pdf.set_xy(x0 + label_kiri, y + indeks * tinggi)
        pdf.cell(nilai_kiri, tinggi, (": " if indeks == 0 else "  ") + teks)
    x1 = x0 + label_kiri + nilai_kiri
    pdf.set_xy(x1, y)
    pdf.cell(label_kanan, tinggi, kanan[0])
    for indeks, teks in enumerate(kanan_baris):
        pdf.set_xy(x1 + label_kanan, y + indeks * tinggi)
        pdf.cell(nilai_kanan, tinggi, (": " if indeks == 0 else "  ") + teks)
    pdf.set_xy(x0, y + jumlah * tinggi)


def tulis_rapor(pdf, rapor):
    pdf.add_page()
    pdf.set_font(pdf.font_rapor, "B", 13)
    judul = "LAPORAN HASIL BELAJAR TENGAH SEMESTER" if rapor["semester_angka"] == 1 else "LAPORAN HASIL BELAJAR AKHIR SEMESTER"
    pdf.cell(0, 8, judul, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    _pasangan(pdf, ("Nama Sekolah", rapor["sekolah"]), ("Kelas", rapor["kelas"]))
    _pasangan(pdf, ("Alamat", rapor["alamat"]), ("Fase", rapor["fase"]))
    _pasangan(pdf, ("Nama Siswa", rapor["siswa"]), ("Semester", rapor["semester"]))
    _pasangan(pdf, ("NISN / NIS", rapor["nisn"]), ("Tahun Ajaran", rapor["tahun"]))
    pdf.ln(2)
    _kepala_tabel(pdf)
    if rapor["mapel"]:
        for nomor, mapel in enumerate(rapor["mapel"], start=1):
            _baris(
                pdf,
                [
                    nomor,
                    mapel["nama"],
                    mapel["kkm"],
                    _angka(mapel["formatif"]),
                    "-",
                    _angka(mapel["sumatif"]),
                    "-",
                ],
            )
    else:
        pdf.set_font(pdf.font_rapor, "", 9)
        pdf.cell(sum(LEBAR), 8, "Belum ada mata pelajaran untuk kelas ini.", border=1, align="C", new_x="LMARGIN", new_y="NEXT")


LEBAR_TAHFIZ = (18, 58, 28, 82)


def _bungkus(pdf, teks, lebar):
    pdf.set_font(pdf.font_rapor, "", 9)
    kata = str(teks or "-").split()
    baris = []
    sekarang = ""
    for bagian in kata or ["-"]:
        calon = (sekarang + " " + bagian).strip()
        if pdf.get_string_width(calon) <= lebar - 3:
            sekarang = calon
        else:
            if sekarang:
                baris.append(sekarang)
            sekarang = bagian
    if sekarang:
        baris.append(sekarang)
    return baris or ["-"]


def _kepala_tahfiz(pdf):
    pdf.set_font(pdf.font_rapor, "B", 9)
    pdf.set_fill_color(245, 245, 245)
    y = pdf.get_y()
    x = pdf.l_margin
    tinggi = 6
    for indeks, judul in ((0, "No. Urut"), (1, "Mata Pelajaran")):
        pdf.rect(x, y, LEBAR_TAHFIZ[indeks], tinggi * 2, style="DF")
        pdf.set_xy(x, y + 3)
        pdf.cell(LEBAR_TAHFIZ[indeks], tinggi, judul, align="C")
        x += LEBAR_TAHFIZ[indeks]
    pdf.rect(x, y, LEBAR_TAHFIZ[2] + LEBAR_TAHFIZ[3], tinggi, style="DF")
    pdf.set_xy(x, y)
    pdf.cell(LEBAR_TAHFIZ[2] + LEBAR_TAHFIZ[3], tinggi, "NILAI", align="C")
    pdf.set_xy(x, y + tinggi)
    pdf.cell(LEBAR_TAHFIZ[2], tinggi, "Angka", border=1, align="C", fill=True)
    pdf.cell(LEBAR_TAHFIZ[3], tinggi, "Deskripsi", border=1, align="C", fill=True)
    pdf.set_xy(pdf.l_margin, y + tinggi * 2)


def tulis_tahfiz(pdf, rapor):
    pdf.add_page()
    pdf.set_font(pdf.font_rapor, "B", 12)
    pdf.cell(0, 6, "LAPORAN HASIL BELAJAR MURID PROGRAM KELAS TAHFIZ", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, str(rapor["sekolah"]).upper(), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"TAHUN AJARAN {rapor['tahun']}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    _pasangan(pdf, ("Nama", rapor["siswa"]), ("Kelas", rapor["kelas"]))
    _pasangan(pdf, ("NIS/NISN", rapor["nisn"]), ("Fase", rapor["fase"]))
    _pasangan(pdf, ("Nama Sekolah", rapor["sekolah"]), ("Semester", str(rapor["semester"])))
    _pasangan(pdf, ("Alamat", rapor["alamat"]), ("Tahun Ajaran", rapor["tahun"]))
    pdf.ln(2)
    _kepala_tahfiz(pdf)
    if not rapor["mapel"]:
        pdf.set_font(pdf.font_rapor, "", 9)
        pdf.cell(sum(LEBAR_TAHFIZ), 8, "Belum ada aspek tahfiz.", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
        return
    for nomor, mapel in enumerate(rapor["mapel"], start=1):
        baris = _bungkus(pdf, mapel["deskripsi"] or "-", LEBAR_TAHFIZ[3])
        tinggi = max(8, len(baris) * 5)
        y = pdf.get_y()
        if y + tinggi > pdf.h - pdf.b_margin:
            pdf.add_page()
            _kepala_tahfiz(pdf)
            y = pdf.get_y()
        x = pdf.l_margin
        pdf.set_font(pdf.font_rapor, "", 9)
        pdf.rect(x, y, LEBAR_TAHFIZ[0], tinggi)
        pdf.set_xy(x, y + (tinggi - 5) / 2)
        pdf.cell(LEBAR_TAHFIZ[0], 5, f"{nomor}.", align="C")
        x += LEBAR_TAHFIZ[0]
        pdf.rect(x, y, LEBAR_TAHFIZ[1], tinggi)
        pdf.set_xy(x + 1, y + (tinggi - 5) / 2)
        pdf.cell(LEBAR_TAHFIZ[1] - 2, 5, str(mapel["nama"]))
        x += LEBAR_TAHFIZ[1]
        pdf.rect(x, y, LEBAR_TAHFIZ[2], tinggi)
        pdf.set_xy(x, y + (tinggi - 5) / 2)
        pdf.cell(LEBAR_TAHFIZ[2], 5, _angka(mapel["nilai"]), align="C")
        x += LEBAR_TAHFIZ[2]
        pdf.rect(x, y, LEBAR_TAHFIZ[3], tinggi)
        pdf.set_xy(x + 1, y + 1.5)
        for teks in baris:
            pdf.cell(LEBAR_TAHFIZ[3] - 2, 5, teks, new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(x + 1)
        pdf.set_xy(pdf.l_margin, y + tinggi)


def buat_pdf_tahfiz(daftar):
    pdf = FPDF(format="A4")
    pdf.font_rapor = _font(pdf)
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(12, 12, 12)
    for rapor in daftar:
        tulis_tahfiz(pdf, rapor)
    if not daftar:
        pdf.add_page()
        pdf.set_font(pdf.font_rapor, "", 12)
        pdf.cell(0, 10, "Tidak ada siswa untuk dicetak.")
    keluar = BytesIO(bytes(pdf.output()))
    keluar.seek(0)
    return keluar


def buat_pdf(daftar):
    pdf = FPDF(format="A4")
    pdf.font_rapor = _font(pdf)
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.set_margins(12, 12, 12)
    for rapor in daftar:
        tulis_rapor(pdf, rapor)
    if not daftar:
        pdf.add_page()
        pdf.set_font(pdf.font_rapor, "", 12)
        pdf.cell(0, 10, "Tidak ada siswa untuk dicetak.")
    keluar = BytesIO(bytes(pdf.output()))
    keluar.seek(0)
    return keluar
