CREATE DATABASE IF NOT EXISTS erapor_smamduma
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE erapor_smamduma;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS nilai_tahfiz;
DROP TABLE IF EXISTS pengaturan_rapor_tahfiz;
DROP TABLE IF EXISTS mapping_guru_tahfiz;
DROP TABLE IF EXISTS aspek_tahfiz;
DROP TABLE IF EXISTS nilai_tryout;
DROP TABLE IF EXISTS tryout;
DROP TABLE IF EXISTS gabung_mapel_item;
DROP TABLE IF EXISTS gabung_mapel;
DROP TABLE IF EXISTS mapping_rapor;
DROP TABLE IF EXISTS nilai_ekskul;
DROP TABLE IF EXISTS ekstrakurikuler;
DROP TABLE IF EXISTS nilai_sumatif;
DROP TABLE IF EXISTS nilai_formatif;
DROP TABLE IF EXISTS perencanaan_penilaian;
DROP TABLE IF EXISTS pelajaran;
DROP TABLE IF EXISTS mata_pelajaran;
DROP TABLE IF EXISTS kelompok_mapel;
DROP TABLE IF EXISTS siswa;
DROP TABLE IF EXISTS kelas;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS guru;
DROP TABLE IF EXISTS tahun_ajaran;
DROP TABLE IF EXISTS sekolah;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE sekolah (
  id INT PRIMARY KEY AUTO_INCREMENT,
  nama VARCHAR(200) NOT NULL,
  npsn VARCHAR(20),
  jenjang VARCHAR(20) DEFAULT 'SMA',
  alamat TEXT,
  kelurahan VARCHAR(100),
  kecamatan VARCHAR(100),
  kabupaten VARCHAR(100),
  provinsi VARCHAR(100),
  kode_pos VARCHAR(10),
  telepon VARCHAR(30),
  email VARCHAR(100),
  website VARCHAR(150),
  kepala_sekolah VARCHAR(150),
  nip_kepala VARCHAR(40),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE tahun_ajaran (
  id INT PRIMARY KEY AUTO_INCREMENT,
  tahun VARCHAR(20) NOT NULL,
  semester TINYINT NOT NULL,
  aktif TINYINT NOT NULL DEFAULT 0
);

CREATE TABLE guru (
  id INT PRIMARY KEY AUTO_INCREMENT,
  nip VARCHAR(30),
  nuptk VARCHAR(30),
  nama VARCHAR(150) NOT NULL,
  gelar_depan VARCHAR(20) DEFAULT '',
  gelar_belakang VARCHAR(80) DEFAULT '',
  jenis_kelamin ENUM('L','P') NULL,
  tempat_lahir VARCHAR(100),
  tanggal_lahir DATE,
  agama VARCHAR(20) DEFAULT 'Islam',
  alamat TEXT,
  no_hp VARCHAR(20),
  email VARCHAR(100),
  status_kepegawaian VARCHAR(50) DEFAULT 'Guru Tetap',
  mapel_ajar TEXT NULL,
  jumlah_jam INT NULL,
  mengajar_di TEXT NULL,
  aktif TINYINT NOT NULL DEFAULT 1
);

CREATE TABLE users (
  id INT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  nama VARCHAR(150) NOT NULL,
  role ENUM('admin','guru','wali_kelas') NOT NULL DEFAULT 'admin',
  guru_id INT NULL,
  CONSTRAINT fk_users_guru FOREIGN KEY (guru_id) REFERENCES guru(id) ON DELETE SET NULL
);

CREATE TABLE kelas (
  id INT PRIMARY KEY AUTO_INCREMENT,
  nama VARCHAR(30) NOT NULL,
  tingkat VARCHAR(10) NOT NULL,
  jurusan VARCHAR(50) DEFAULT 'Umum',
  wali_kelas_id INT NULL,
  tahun_ajaran_id INT NOT NULL,
  kapasitas INT DEFAULT 36,
  CONSTRAINT fk_kelas_wali FOREIGN KEY (wali_kelas_id) REFERENCES guru(id) ON DELETE SET NULL,
  CONSTRAINT fk_kelas_ta FOREIGN KEY (tahun_ajaran_id) REFERENCES tahun_ajaran(id) ON DELETE CASCADE
);

CREATE TABLE siswa (
  id INT PRIMARY KEY AUTO_INCREMENT,
  nis VARCHAR(20) NOT NULL,
  nisn VARCHAR(20),
  nama VARCHAR(150) NOT NULL,
  jenis_kelamin ENUM('L','P') DEFAULT 'L',
  tempat_lahir VARCHAR(100),
  tanggal_lahir DATE,
  agama VARCHAR(20) DEFAULT 'Islam',
  alamat TEXT,
  nama_ayah VARCHAR(150),
  nama_ibu VARCHAR(150),
  no_hp VARCHAR(20),
  kelas_id INT NULL,
  status ENUM('aktif','lulus','pindah','dropout') DEFAULT 'aktif',
  CONSTRAINT fk_siswa_kelas FOREIGN KEY (kelas_id) REFERENCES kelas(id) ON DELETE SET NULL,
  UNIQUE KEY uk_siswa_nis (nis)
);

CREATE TABLE kelompok_mapel (
  id INT PRIMARY KEY AUTO_INCREMENT,
  kode VARCHAR(20) NOT NULL,
  nama VARCHAR(120) NOT NULL,
  urutan INT DEFAULT 0
);

CREATE TABLE mata_pelajaran (
  id INT PRIMARY KEY AUTO_INCREMENT,
  kode VARCHAR(20) NOT NULL,
  nama VARCHAR(150) NOT NULL,
  kelompok_id INT NULL,
  kkm_default INT DEFAULT 75,
  CONSTRAINT fk_mapel_kelompok FOREIGN KEY (kelompok_id) REFERENCES kelompok_mapel(id) ON DELETE SET NULL
);

CREATE TABLE pelajaran (
  id INT PRIMARY KEY AUTO_INCREMENT,
  tahun_ajaran_id INT NOT NULL,
  kelas_id INT NOT NULL,
  mapel_id INT NOT NULL,
  guru_id INT NOT NULL,
  jam_per_minggu INT DEFAULT 2,
  CONSTRAINT fk_pel_ta FOREIGN KEY (tahun_ajaran_id) REFERENCES tahun_ajaran(id) ON DELETE CASCADE,
  CONSTRAINT fk_pel_kelas FOREIGN KEY (kelas_id) REFERENCES kelas(id) ON DELETE CASCADE,
  CONSTRAINT fk_pel_mapel FOREIGN KEY (mapel_id) REFERENCES mata_pelajaran(id) ON DELETE CASCADE,
  CONSTRAINT fk_pel_guru FOREIGN KEY (guru_id) REFERENCES guru(id) ON DELETE CASCADE,
  UNIQUE KEY uk_pelajaran (tahun_ajaran_id, kelas_id, mapel_id)
);

CREATE TABLE perencanaan_penilaian (
  id INT PRIMARY KEY AUTO_INCREMENT,
  pelajaran_id INT NOT NULL,
  jumlah_tp INT DEFAULT 4,
  kkm INT DEFAULT 75,
  mapped TINYINT NOT NULL DEFAULT 1,
  keterangan VARCHAR(255),
  CONSTRAINT fk_rencana_pel FOREIGN KEY (pelajaran_id) REFERENCES pelajaran(id) ON DELETE CASCADE,
  UNIQUE KEY uk_rencana (pelajaran_id)
);

CREATE TABLE nilai_formatif (
  id INT PRIMARY KEY AUTO_INCREMENT,
  pelajaran_id INT NOT NULL,
  siswa_id INT NOT NULL,
  nilai DECIMAL(5,2) NOT NULL,
  CONSTRAINT fk_nf_pel FOREIGN KEY (pelajaran_id) REFERENCES pelajaran(id) ON DELETE CASCADE,
  CONSTRAINT fk_nf_siswa FOREIGN KEY (siswa_id) REFERENCES siswa(id) ON DELETE CASCADE,
  UNIQUE KEY uk_nf (pelajaran_id, siswa_id)
);

CREATE TABLE nilai_sumatif (
  id INT PRIMARY KEY AUTO_INCREMENT,
  pelajaran_id INT NOT NULL,
  siswa_id INT NOT NULL,
  nilai DECIMAL(5,2) NOT NULL,
  CONSTRAINT fk_ns_pel FOREIGN KEY (pelajaran_id) REFERENCES pelajaran(id) ON DELETE CASCADE,
  CONSTRAINT fk_ns_siswa FOREIGN KEY (siswa_id) REFERENCES siswa(id) ON DELETE CASCADE,
  UNIQUE KEY uk_ns (pelajaran_id, siswa_id)
);

CREATE TABLE ekstrakurikuler (
  id INT PRIMARY KEY AUTO_INCREMENT,
  nama VARCHAR(120) NOT NULL,
  pembina_id INT NULL,
  CONSTRAINT fk_ekskul_pembina FOREIGN KEY (pembina_id) REFERENCES guru(id) ON DELETE SET NULL
);

CREATE TABLE mapping_rapor (
  id INT PRIMARY KEY AUTO_INCREMENT,
  mapel_id INT NOT NULL,
  tampil_rapor TINYINT DEFAULT 1,
  urutan INT DEFAULT 0,
  CONSTRAINT fk_maprapor_mapel FOREIGN KEY (mapel_id) REFERENCES mata_pelajaran(id) ON DELETE CASCADE
);

CREATE TABLE gabung_mapel (
  id INT PRIMARY KEY AUTO_INCREMENT,
  nama_gabungan VARCHAR(150) NOT NULL
);

CREATE TABLE gabung_mapel_item (
  id INT PRIMARY KEY AUTO_INCREMENT,
  gabung_id INT NOT NULL,
  mapel_id INT NOT NULL,
  CONSTRAINT fk_gmi_gabung FOREIGN KEY (gabung_id) REFERENCES gabung_mapel(id) ON DELETE CASCADE,
  CONSTRAINT fk_gmi_mapel FOREIGN KEY (mapel_id) REFERENCES mata_pelajaran(id) ON DELETE CASCADE
);

CREATE TABLE tryout (
  id INT PRIMARY KEY AUTO_INCREMENT,
  nama VARCHAR(150) NOT NULL,
  tanggal DATE,
  tingkat VARCHAR(10) DEFAULT 'XII'
);

CREATE TABLE aspek_tahfiz (
  id INT PRIMARY KEY AUTO_INCREMENT,
  nama VARCHAR(150) NOT NULL,
  jenis VARCHAR(50) DEFAULT 'Hafalan',
  kkm INT DEFAULT 75
);

CREATE TABLE mapping_guru_tahfiz (
  id INT PRIMARY KEY AUTO_INCREMENT,
  guru_id INT NOT NULL,
  kelas_id INT NOT NULL,
  aspek_id INT NOT NULL,
  CONSTRAINT fk_mgt_guru FOREIGN KEY (guru_id) REFERENCES guru(id) ON DELETE CASCADE,
  CONSTRAINT fk_mgt_kelas FOREIGN KEY (kelas_id) REFERENCES kelas(id) ON DELETE CASCADE,
  CONSTRAINT fk_mgt_aspek FOREIGN KEY (aspek_id) REFERENCES aspek_tahfiz(id) ON DELETE CASCADE
);

CREATE TABLE pengaturan_rapor_tahfiz (
  id INT PRIMARY KEY AUTO_INCREMENT,
  tampilkan TINYINT DEFAULT 1,
  judul VARCHAR(150) DEFAULT 'Rapor Tahfiz',
  keterangan TEXT
);

CREATE TABLE nilai_tahfiz (
  id INT PRIMARY KEY AUTO_INCREMENT,
  siswa_id INT NOT NULL,
  aspek_id INT NOT NULL,
  tahun_ajaran_id INT NOT NULL,
  nilai DECIMAL(5,2),
  predikat VARCHAR(10),
  deskripsi TEXT,
  CONSTRAINT fk_nt_siswa FOREIGN KEY (siswa_id) REFERENCES siswa(id) ON DELETE CASCADE,
  CONSTRAINT fk_nt_aspek FOREIGN KEY (aspek_id) REFERENCES aspek_tahfiz(id) ON DELETE CASCADE,
  CONSTRAINT fk_nt_ta FOREIGN KEY (tahun_ajaran_id) REFERENCES tahun_ajaran(id) ON DELETE CASCADE,
  UNIQUE KEY uk_nt (siswa_id, aspek_id, tahun_ajaran_id)
);
