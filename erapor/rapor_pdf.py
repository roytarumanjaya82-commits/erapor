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


def _tengah(pdf, x, y, lebar, tinggi, teks, ukuran=8):
    pdf.set_font(pdf.font_rapor, "B", ukuran)
    pdf.rect(x, y, lebar, tinggi, style="DF")
    baris = _bungkus(pdf, teks, lebar - 1, ukuran)
    pdf.set_font(pdf.font_rapor, "B", ukuran)
    awal = y + max(0, (tinggi - len(baris) * 3.6) / 2)
    for indeks, bagian in enumerate(baris):
        pdf.set_xy(x, awal + indeks * 3.6)
        pdf.cell(lebar, 3.6, bagian, align="C")


def _baris(pdf, isi):
    pdf.set_font(pdf.font_rapor, "", 8)
    nama = _bungkus(pdf, isi[1], LEBAR[1] - 2, 8)
    tinggi = max(6.2, len(nama) * 4)
    y = pdf.get_y()
    if y + tinggi > pdf.h - pdf.b_margin:
        pdf.add_page()
        _kepala_tabel(pdf)
        y = pdf.get_y()
    x = pdf.l_margin
    for lebar in LEBAR:
        pdf.rect(x, y, lebar, tinggi)
        x += lebar
    x = pdf.l_margin
    pdf.set_xy(x, y + (tinggi - 4) / 2)
    pdf.cell(LEBAR[0], 4, str(isi[0]), align="C")
    x += LEBAR[0]
    pdf.set_xy(x + 1, y + 1)
    for bagian in nama:
        pdf.cell(LEBAR[1] - 2, 4, bagian, new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(x + 1)
    x += LEBAR[1]
    for indeks, teks in enumerate(isi[2:], start=2):
        pdf.set_xy(x, y + (tinggi - 4) / 2)
        pdf.cell(LEBAR[indeks], 4, str(teks), align="C")
        x += LEBAR[indeks]
    pdf.set_xy(pdf.l_margin, y + tinggi)


def _kepala_tabel(pdf):
    pdf.set_font(pdf.font_rapor, "B", 8)
    pdf.set_fill_color(245, 245, 245)
    y = pdf.get_y()
    x = pdf.l_margin
    tinggi = 6
    for indeks, judul in ((0, "No"), (1, "Mata Pelajaran"), (2, "KKM")):
        _tengah(pdf, x, y, LEBAR[indeks], tinggi * 2, judul)
        x += LEBAR[indeks]
    _tengah(pdf, x, y, LEBAR[3] + LEBAR[4], tinggi, "Asesmen Formatif", 7)
    _tengah(pdf, x + LEBAR[3] + LEBAR[4], y, LEBAR[5], tinggi, "Asesmen Sumatif", 6.5)
    _tengah(pdf, x + LEBAR[3] + LEBAR[4] + LEBAR[5], y, LEBAR[6], tinggi * 2, "ASTS")
    pdf.set_xy(x, y + tinggi)
    for indeks, judul in ((3, "Formatif 1"), (4, "Formatif 2"), (5, "Sumatif")):
        pdf.set_font(pdf.font_rapor, "B", 7)
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
                    _angka(mapel.get("formatif")),
                    _angka(mapel.get("formatif_2")),
                    _angka(mapel.get("sumatif")),
                    _angka(mapel.get("asts")),
                ],
            )
    else:
        pdf.set_font(pdf.font_rapor, "", 9)
        pdf.cell(sum(LEBAR), 8, "Belum ada mata pelajaran untuk kelas ini.", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
    _sikap(pdf, rapor)
    _kehadiran_ekskul(pdf, rapor)
    _tanda_tangan(pdf, rapor)


def _sikap(pdf, rapor):
    pdf.ln(3)
    pdf.set_font(pdf.font_rapor, "B", 10)
    pdf.cell(0, 5, "Sikap:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(pdf.font_rapor, "", 9)
    teks = rapor.get("sikap") or "Belum ada deskripsi sikap."
    pdf.multi_cell(sum(LEBAR), 5, teks, border=1)


def _judul_kolom(pdf, judul, lebar):
    pdf.set_font(pdf.font_rapor, "B", 8)
    pdf.set_fill_color(245, 245, 245)
    for teks, ukuran in zip(judul, lebar):
        pdf.cell(ukuran, 6, teks, border=1, align="C", fill=True)
    pdf.ln(6)


def _kehadiran_ekskul(pdf, rapor):
    pdf.ln(3)
    y = pdf.get_y()
    kiri = 74
    pdf.set_font(pdf.font_rapor, "B", 10)
    pdf.cell(kiri, 5, "Presensi :", new_x="LMARGIN", new_y="NEXT")
    lebar_hadir = (46, 28)
    _judul_kolom(pdf, ("Ketidakhadiran", "Keterangan"), lebar_hadir)
    pdf.set_font(pdf.font_rapor, "", 8)
    for label, nilai in rapor.get("presensi") or ():
        pdf.cell(lebar_hadir[0], 6, label, border=1)
        pdf.cell(lebar_hadir[1], 6, nilai, border=1, align="C", new_x="LMARGIN", new_y="NEXT")
    bawah_kiri = pdf.get_y()
    kanan_x = pdf.l_margin + kiri + 6
    pdf.set_xy(kanan_x, y)
    pdf.set_font(pdf.font_rapor, "B", 10)
    pdf.cell(sum(LEBAR) - kiri - 6, 5, "Pengembangan Diri / Ekstrakurikuler:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(kanan_x)
    lebar_ekskul = (10, 68, 28)
    pdf.set_font(pdf.font_rapor, "B", 8)
    pdf.set_fill_color(245, 245, 245)
    for teks, ukuran in zip(("No", "Pengembangan Diri / Ekstrakurikuler", "Nilai"), lebar_ekskul):
        pdf.cell(ukuran, 6, teks, border=1, align="C", fill=True)
    pdf.ln(6)
    pdf.set_font(pdf.font_rapor, "", 8)
    ekskul = rapor.get("ekskul") or []
    if not ekskul:
        pdf.set_x(kanan_x)
        pdf.cell(sum(lebar_ekskul), 6, "Belum ada ekstrakurikuler.", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
    for nomor, item in enumerate(ekskul, start=1):
        pdf.set_x(kanan_x)
        pdf.cell(lebar_ekskul[0], 6, str(nomor), border=1, align="C")
        pdf.cell(lebar_ekskul[1], 6, str(item.get("nama") or "-"), border=1)
        pdf.cell(lebar_ekskul[2], 6, str(item.get("nilai") or "-"), border=1, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(max(bawah_kiri, pdf.get_y()))


def _kolom_tanda(pdf, x, y, lebar, baris, tebal=False):
    pdf.set_xy(x, y)
    for indeks, teks in enumerate(baris):
        pdf.set_x(x)
        pdf.set_font(pdf.font_rapor, "B" if tebal and indeks == 0 else "", 9)
        pdf.cell(lebar, 5, teks, align="C", new_x="LMARGIN", new_y="NEXT")
    return pdf.get_y()


def _tanda_tangan(pdf, rapor):
    pdf.ln(8)
    if pdf.get_y() > pdf.h - 45:
        pdf.add_page()
    y = pdf.get_y()
    lebar = sum(LEBAR) / 3
    x0 = pdf.l_margin
    tempat = ", ".join(bagian for bagian in (rapor.get("tempat") or "", rapor.get("tanggal") or "") if bagian)
    _kolom_tanda(pdf, x0, y, lebar, ["Mengetahui,", "Orang Tua / Wali Siswa,"])
    _kolom_tanda(pdf, x0 + lebar, y, lebar, ["Wali Kelas,"])
    kepala = ["Kepala Sekolah,"]
    if tempat:
        kepala.insert(0, tempat)
    _kolom_tanda(pdf, x0 + lebar * 2, y, lebar, kepala)
    y_nama = y + 22
    pdf.set_xy(x0, y_nama)
    pdf.set_font(pdf.font_rapor, "", 9)
    pdf.cell(lebar, 5, "................................", align="C")
    wali = [rapor.get("wali") or ""]
    if rapor.get("nbm_wali"):
        wali.append(f"NBM. {rapor['nbm_wali']}")
    _kolom_tanda(pdf, x0 + lebar, y_nama, lebar, wali, tebal=True)
    sekolah = [rapor.get("kepala") or ""]
    if rapor.get("nbm_kepala"):
        sekolah.append(f"NBM. {rapor['nbm_kepala']}")
    _kolom_tanda(pdf, x0 + lebar * 2, y_nama, lebar, sekolah, tebal=True)
    pdf.set_y(y_nama + 12)


LEBAR_TAHFIZ = (18, 58, 28, 82)


def _bungkus(pdf, teks, lebar, ukuran=9):
    pdf.set_font(pdf.font_rapor, "", ukuran)
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
        pdf.set_font(pdf.font_rapor, "B", 10)
        pdf.set_xy(x, y + (tinggi - 5) / 2)
        pdf.cell(LEBAR_TAHFIZ[2], 5, _angka(mapel["nilai"]), align="C")
        pdf.set_font(pdf.font_rapor, "", 9)
        x += LEBAR_TAHFIZ[2]
        pdf.rect(x, y, LEBAR_TAHFIZ[3], tinggi)
        pdf.set_xy(x + 1, y + 1.5)
        for teks in baris:
            pdf.cell(LEBAR_TAHFIZ[3] - 2, 5, teks, new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(x + 1)
        pdf.set_xy(pdf.l_margin, y + tinggi)
    _tanda_tahfiz(pdf, rapor)


def _tanda_tahfiz(pdf, rapor):
    pdf.ln(8)
    lebar = sum(LEBAR_TAHFIZ)
    x0 = pdf.l_margin
    pdf.set_font(pdf.font_rapor, "", 9)
    tempat = ", ".join(bagian for bagian in (rapor.get("tempat") or "", rapor.get("tanggal_hijriah") or "") if bagian)
    if tempat:
        pdf.cell(lebar, 5, tempat, align="R", new_x="LMARGIN", new_y="NEXT")
    if rapor.get("tanggal_masehi"):
        pdf.cell(lebar, 5, str(rapor["tanggal_masehi"]), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    y = pdf.get_y()
    kolom = lebar / 3
    _kolom_tanda(pdf, x0, y, kolom, ["Mengetahui,", "Orang Tua / Wali Siswa"])
    _kolom_tanda(pdf, x0 + kolom, y, kolom, ["Wali Kelas"])
    _kolom_tanda(pdf, x0 + kolom * 2, y, kolom, ["Mengetahui,", "Kepala Sekolah"])
    y_nama = y + 18
    pdf.set_xy(x0, y_nama)
    pdf.set_font(pdf.font_rapor, "", 9)
    pdf.cell(kolom, 5, "........................", align="C")
    wali = [rapor.get("wali") or ""]
    if rapor.get("nbm_wali"):
        wali.append(f"NBM. {rapor['nbm_wali']}")
    _kolom_tanda(pdf, x0 + kolom, y_nama, kolom, wali, tebal=True)
    kepala = [rapor.get("kepala") or ""]
    if rapor.get("nbm_kepala"):
        kepala.append(f"NBM. {rapor['nbm_kepala']}")
    _kolom_tanda(pdf, x0 + kolom * 2, y_nama, kolom, kepala, tebal=True)


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
