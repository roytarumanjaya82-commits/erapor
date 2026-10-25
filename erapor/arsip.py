import gzip
import hashlib
import hmac
import os
from datetime import datetime

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from flask import current_app

MAGIC = b"ERAPORBAK1"
MAKS_BYTE = 100 * 1024 * 1024


def folder_backup():
    folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "app", "private", "backups")
    os.makedirs(folder, exist_ok=True)
    return folder


def kata_kunci(isian):
    teks = (isian or "").strip()
    if teks:
        return teks, True
    return current_app.config["SECRET_KEY"], False


def _kunci(kata, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=64, salt=salt, iterations=120000)
    bahan = kdf.derive(kata.encode("utf-8"))
    return bahan[:32], bahan[32:]


def bungkus(sql_bytes, isian):
    kata, kustom = kata_kunci(isian)
    salt = os.urandom(16)
    iv = os.urandom(16)
    kunci, kunci_mac = _kunci(kata, salt)
    terkompres = gzip.compress(sql_bytes)
    pad = 16 - (len(terkompres) % 16)
    terisi = terkompres + bytes([pad]) * pad
    penyandi = Cipher(algorithms.AES(kunci), modes.CBC(iv)).encryptor()
    rahasia = penyandi.update(terisi) + penyandi.finalize()
    flag = b"\x01" if kustom else b"\x00"
    tag = hmac.new(kunci_mac, flag + salt + iv + rahasia, hashlib.sha256).digest()
    return MAGIC + flag + salt + iv + tag + rahasia


def buka(blob, isian):
    if blob.startswith(b"-- eRapor backup"):
        return blob.decode("utf-8")
    if len(blob) > MAKS_BYTE:
        raise ValueError("ukuran")
    if not blob.startswith(MAGIC) or len(blob) < 75:
        raise ValueError("format")
    flag = blob[10:11]
    salt = blob[11:27]
    iv = blob[27:43]
    tag = blob[43:75]
    rahasia = blob[75:]
    kata, _kustom = kata_kunci(isian)
    kunci, kunci_mac = _kunci(kata, salt)
    hitung = hmac.new(kunci_mac, flag + salt + iv + rahasia, hashlib.sha256).digest()
    if not hmac.compare_digest(hitung, tag):
        raise ValueError("kunci")
    pengurai = Cipher(algorithms.AES(kunci), modes.CBC(iv)).decryptor()
    terisi = pengurai.update(rahasia) + pengurai.finalize()
    pad = terisi[-1]
    if pad < 1 or pad > 16 or terisi[-pad:] != bytes([pad]) * pad:
        raise ValueError("rusak")
    return gzip.decompress(terisi[:-pad]).decode("utf-8")


def nama_aman(nama):
    dasar = os.path.basename(nama or "")
    if not dasar.endswith(".eraporbak") or "/" in dasar or "\\" in dasar or dasar.startswith("."):
        return ""
    return dasar


def simpan_backup(blob):
    nama = f"erapor-{datetime.now():%Y%m%d-%H%M%S-%f}.eraporbak"
    jalur = os.path.join(folder_backup(), nama)
    with open(jalur, "wb") as berkas:
        berkas.write(blob)
    return nama


def daftar_backup():
    hasil = []
    for nama in os.listdir(folder_backup()):
        if not nama_aman(nama):
            continue
        jalur = os.path.join(folder_backup(), nama)
        stat = os.stat(jalur)
        hasil.append(
            {
                "nama": nama,
                "ukuran": _ukuran(stat.st_size),
                "waktu": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M"),
            }
        )
    hasil.sort(key=lambda item: item["nama"], reverse=True)
    return hasil


def _ukuran(jumlah):
    if jumlah < 1024:
        return f"{jumlah} B"
    if jumlah < 1024 * 1024:
        return f"{jumlah / 1024:.1f} KB"
    return f"{jumlah / (1024 * 1024):.1f} MB"
