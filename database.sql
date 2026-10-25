-- Pembaruan database eRapor SMPM22SETIABUDIPAMULANG yang sudah terisi.
-- Menambah tabel yang belum ada, kolom NBM, peran siswa,
-- dan menyamakan tingkat kelas menjadi 7, 8, dan 9.
-- Tidak menghapus guru, siswa, atau nilai.
-- Instalasi baru: jalankan schema.sql, lalu python seed.py.

USE erapor_smamduma;

ALTER TABLE users
  MODIFY role ENUM('admin','guru','wali_kelas','siswa') NOT NULL DEFAULT 'guru';

SET @ada_email := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'email'
);
SET @sql_email := IF(@ada_email = 0, 'ALTER TABLE users ADD COLUMN email VARCHAR(150) NULL', 'SELECT 1');
PREPARE stmt_email FROM @sql_email;
EXECUTE stmt_email;
DEALLOCATE PREPARE stmt_email;

SET @ada_aktif := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'aktif'
);
SET @sql_aktif := IF(@ada_aktif = 0, 'ALTER TABLE users ADD COLUMN aktif TINYINT NOT NULL DEFAULT 1', 'SELECT 1');
PREPARE stmt_aktif FROM @sql_aktif;
EXECUTE stmt_aktif;
DEALLOCATE PREPARE stmt_aktif;

SET @ada_login := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'login_terakhir'
);
SET @sql_login := IF(@ada_login = 0, 'ALTER TABLE users ADD COLUMN login_terakhir DATETIME NULL', 'SELECT 1');
PREPARE stmt_login FROM @sql_login;
EXECUTE stmt_login;
DEALLOCATE PREPARE stmt_login;

SET @ada_ip := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'ip_address'
);
SET @sql_ip := IF(@ada_ip = 0, 'ALTER TABLE users ADD COLUMN ip_address VARCHAR(45) NULL', 'SELECT 1');
PREPARE stmt_ip FROM @sql_ip;
EXECUTE stmt_ip;
DEALLOCATE PREPARE stmt_ip;

SET @ada_online := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'sedang_login'
);
SET @sql_online := IF(@ada_online = 0, 'ALTER TABLE users ADD COLUMN sedang_login TINYINT NOT NULL DEFAULT 0', 'SELECT 1');
PREPARE stmt_online FROM @sql_online;
EXECUTE stmt_online;
DEALLOCATE PREPARE stmt_online;

SET @ada_nbm := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'guru' AND COLUMN_NAME = 'nbm'
);
SET @sql_nbm := IF(@ada_nbm = 0, 'ALTER TABLE guru ADD COLUMN nbm VARCHAR(30) NULL', 'SELECT 1');
PREPARE stmt_nbm FROM @sql_nbm;
EXECUTE stmt_nbm;
DEALLOCATE PREPARE stmt_nbm;

CREATE TABLE IF NOT EXISTS user_tugas (
  user_id INT NOT NULL,
  tugas VARCHAR(30) NOT NULL,
  PRIMARY KEY (user_id, tugas),
  CONSTRAINT fk_ut_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dimensi_sikap (
  id INT PRIMARY KEY AUTO_INCREMENT,
  kode VARCHAR(60) NULL,
  nama VARCHAR(150) NOT NULL,
  indikator TEXT,
  kelas_7 TINYINT DEFAULT 1,
  kelas_8 TINYINT DEFAULT 1,
  kelas_9 TINYINT DEFAULT 1,
  urutan INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS predikat_sikap (
  id INT PRIMARY KEY AUTO_INCREMENT,
  nama VARCHAR(50) NOT NULL,
  deskripsi VARCHAR(255),
  aktif TINYINT DEFAULT 1,
  urutan INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS nilai_ekskul (
  id INT PRIMARY KEY AUTO_INCREMENT,
  ekskul_id INT NOT NULL,
  siswa_id INT NOT NULL,
  nilai VARCHAR(30),
  UNIQUE KEY uk_nilai_ekskul (ekskul_id, siswa_id)
);

INSERT INTO dimensi_sikap (nama, indikator, urutan)
SELECT v.nama, v.indikator, v.urutan
FROM (
  SELECT 'Keimanan dan ketakwaan kepada Tuhan YME' AS nama, 'Berdoa, menjalankan ibadah, menghormati keyakinan, berakhlak baik' AS indikator, 1 AS urutan
  UNION ALL SELECT 'Penalaran kritis', 'Bertanya dengan baik, mempertimbangkan informasi sebelum bertindak', 2
  UNION ALL SELECT 'Kreativitas', 'Memiliki inisiatif, mencoba cara baru, menghasilkan gagasan positif', 3
  UNION ALL SELECT 'Gotong royong', 'Mau bekerja sama, berbagi tugas, dan membantu teman', 4
) v
WHERE NOT EXISTS (SELECT 1 FROM dimensi_sikap);

INSERT INTO predikat_sikap (nama, deskripsi, urutan)
SELECT v.nama, v.deskripsi, v.urutan
FROM (
  SELECT 'Berkembang' AS nama, 'Menunjukkan perkembangan pada dimensi' AS deskripsi, 1 AS urutan
  UNION ALL SELECT 'Cakap', 'Menunjukkan kemampuan yang cakap pada dimensi', 2
  UNION ALL SELECT 'Mahir', 'Menunjukkan penguasaan yang mahir pada dimensi', 3
) v
WHERE NOT EXISTS (SELECT 1 FROM predikat_sikap);

UPDATE kelas
SET nama = CONCAT('9', SUBSTRING(nama, 4)), tingkat = '9'
WHERE nama LIKE 'XII%';

UPDATE kelas
SET nama = CONCAT('8', SUBSTRING(nama, 3)), tingkat = '8'
WHERE nama LIKE 'XI%' AND nama NOT LIKE 'XII%';

UPDATE kelas
SET nama = CONCAT('7', SUBSTRING(nama, 2)), tingkat = '7'
WHERE nama LIKE 'X%' AND nama NOT LIKE 'XI%';

UPDATE kelas
SET nama = CONCAT('8', SUBSTRING(nama, 5)), tingkat = '8'
WHERE nama LIKE 'VIII%';

UPDATE kelas
SET nama = CONCAT('9', SUBSTRING(nama, 3)), tingkat = '9'
WHERE nama LIKE 'IX%';

UPDATE kelas
SET nama = CONCAT('7', SUBSTRING(nama, 4)), tingkat = '7'
WHERE nama LIKE 'VII%';

UPDATE kelas SET tingkat = '7' WHERE tingkat IN ('X', 'VII');
UPDATE kelas SET tingkat = '8' WHERE tingkat IN ('XI', 'VIII');
UPDATE kelas SET tingkat = '9' WHERE tingkat IN ('XII', 'IX');

UPDATE tryout SET tingkat = '9' WHERE tingkat IN ('10', '11', '12', 'X', 'XI', 'XII', 'VII', 'VIII', 'IX');
UPDATE sekolah SET jenjang = 'SMP' WHERE jenjang = 'SMA';

SET @ada_status_sekolah := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sekolah' AND COLUMN_NAME = 'status_sekolah'
);
SET @sql_status_sekolah := IF(@ada_status_sekolah = 0, 'ALTER TABLE sekolah ADD COLUMN status_sekolah VARCHAR(30) NULL', 'SELECT 1');
PREPARE stmt_status_sekolah FROM @sql_status_sekolah;
EXECUTE stmt_status_sekolah;
DEALLOCATE PREPARE stmt_status_sekolah;

SET @ada_tempat_rapor := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sekolah' AND COLUMN_NAME = 'tempat_rapor'
);
SET @sql_tempat_rapor := IF(@ada_tempat_rapor = 0, 'ALTER TABLE sekolah ADD COLUMN tempat_rapor VARCHAR(100) NULL', 'SELECT 1');
PREPARE stmt_tempat_rapor FROM @sql_tempat_rapor;
EXECUTE stmt_tempat_rapor;
DEALLOCATE PREPARE stmt_tempat_rapor;

SET @ada_tanggal_rapor := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sekolah' AND COLUMN_NAME = 'tanggal_rapor'
);
SET @sql_tanggal_rapor := IF(@ada_tanggal_rapor = 0, 'ALTER TABLE sekolah ADD COLUMN tanggal_rapor DATE NULL', 'SELECT 1');
PREPARE stmt_tanggal_rapor FROM @sql_tanggal_rapor;
EXECUTE stmt_tanggal_rapor;
DEALLOCATE PREPARE stmt_tanggal_rapor;

SET @ada_nik := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'siswa' AND COLUMN_NAME = 'nik'
);
SET @sql_nik := IF(@ada_nik = 0, 'ALTER TABLE siswa ADD COLUMN nik VARCHAR(20) NULL', 'SELECT 1');
PREPARE stmt_nik FROM @sql_nik;
EXECUTE stmt_nik;
DEALLOCATE PREPARE stmt_nik;

ALTER TABLE siswa MODIFY jenis_kelamin ENUM('L','P') NULL;

SET @ada_kode_pelajaran := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'pelajaran' AND COLUMN_NAME = 'kode'
);
SET @sql_kode_pelajaran := IF(@ada_kode_pelajaran = 0, 'ALTER TABLE pelajaran ADD COLUMN kode VARCHAR(36) NULL', 'SELECT 1');
PREPARE stmt_kode_pelajaran FROM @sql_kode_pelajaran;
EXECUTE stmt_kode_pelajaran;
DEALLOCATE PREPARE stmt_kode_pelajaran;

SET @ada_status_kurikulum := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'pelajaran' AND COLUMN_NAME = 'status_kurikulum'
);
SET @sql_status_kurikulum := IF(@ada_status_kurikulum = 0, 'ALTER TABLE pelajaran ADD COLUMN status_kurikulum VARCHAR(30) NULL', 'SELECT 1');
PREPARE stmt_status_kurikulum FROM @sql_status_kurikulum;
EXECUTE stmt_status_kurikulum;
DEALLOCATE PREPARE stmt_status_kurikulum;

ALTER TABLE kelompok_mapel MODIFY kode VARCHAR(60) NOT NULL;
UPDATE kelompok_mapel SET nama = 'Kelompok C (Pilihan / Peminatan)' WHERE kode = 'C' AND nama = 'Kelompok C (Peminatan)';
UPDATE kelompok_mapel SET kode = 'Muatan Lokal' WHERE kode = 'M' AND nama = 'Muatan Lokal';

ALTER TABLE pelajaran MODIFY guru_id INT NULL;
ALTER TABLE pelajaran MODIFY jam_per_minggu INT NULL;
UPDATE pelajaran SET kode = LOWER(UUID()) WHERE kode IS NULL OR kode = '';

SET @ada_nama_pembina := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ekstrakurikuler' AND COLUMN_NAME = 'nama_pembina'
);
SET @sql_nama_pembina := IF(@ada_nama_pembina = 0, 'ALTER TABLE ekstrakurikuler ADD COLUMN nama_pembina VARCHAR(150) NULL', 'SELECT 1');
PREPARE stmt_nama_pembina FROM @sql_nama_pembina;
EXECUTE stmt_nama_pembina;
DEALLOCATE PREPARE stmt_nama_pembina;

CREATE TABLE IF NOT EXISTS peserta_ekskul (
  id INT PRIMARY KEY AUTO_INCREMENT,
  ekskul_id INT NOT NULL,
  siswa_id INT NOT NULL,
  UNIQUE KEY uk_peserta_ekskul (ekskul_id, siswa_id)
);

SET @ada_map_kurikulum := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mapping_rapor' AND COLUMN_NAME = 'kurikulum'
);
SET @sql_map_kurikulum := IF(@ada_map_kurikulum = 0, 'ALTER TABLE mapping_rapor ADD COLUMN kurikulum VARCHAR(80) NULL', 'SELECT 1');
PREPARE stmt_map_kurikulum FROM @sql_map_kurikulum;
EXECUTE stmt_map_kurikulum;
DEALLOCATE PREPARE stmt_map_kurikulum;

SET @ada_map_tingkat := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mapping_rapor' AND COLUMN_NAME = 'tingkat'
);
SET @sql_map_tingkat := IF(@ada_map_tingkat = 0, 'ALTER TABLE mapping_rapor ADD COLUMN tingkat VARCHAR(10) NULL', 'SELECT 1');
PREPARE stmt_map_tingkat FROM @sql_map_tingkat;
EXECUTE stmt_map_tingkat;
DEALLOCATE PREPARE stmt_map_tingkat;

SET @ada_map_lokal := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mapping_rapor' AND COLUMN_NAME = 'nama_lokal'
);
SET @sql_map_lokal := IF(@ada_map_lokal = 0, 'ALTER TABLE mapping_rapor ADD COLUMN nama_lokal VARCHAR(150) NULL', 'SELECT 1');
PREPARE stmt_map_lokal FROM @sql_map_lokal;
EXECUTE stmt_map_lokal;
DEALLOCATE PREPARE stmt_map_lokal;

SET @ada_map_kelompok := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mapping_rapor' AND COLUMN_NAME = 'kelompok_id'
);
SET @sql_map_kelompok := IF(@ada_map_kelompok = 0, 'ALTER TABLE mapping_rapor ADD COLUMN kelompok_id INT NULL', 'SELECT 1');
PREPARE stmt_map_kelompok FROM @sql_map_kelompok;
EXECUTE stmt_map_kelompok;
DEALLOCATE PREPARE stmt_map_kelompok;

UPDATE mapping_rapor mr
JOIN mata_pelajaran m ON m.id = mr.mapel_id
SET mr.nama_lokal = m.nama
WHERE mr.nama_lokal IS NULL OR mr.nama_lokal = '';

UPDATE mapping_rapor mr
JOIN mata_pelajaran m ON m.id = mr.mapel_id
SET mr.kelompok_id = m.kelompok_id
WHERE mr.kelompok_id IS NULL;

UPDATE mapping_rapor SET kurikulum = 'Kurikulum Merdeka' WHERE kurikulum IS NULL OR kurikulum = '';
UPDATE mapping_rapor SET tingkat = '7' WHERE tingkat IS NULL OR tingkat = '';

INSERT INTO mapping_rapor (mapel_id, tampil_rapor, urutan, kurikulum, tingkat, nama_lokal, kelompok_id)
SELECT src.mapel_id, src.tampil_rapor, src.urutan, src.kurikulum, '8', src.nama_lokal, src.kelompok_id
FROM mapping_rapor src
WHERE src.tingkat = '7'
AND NOT EXISTS (
  SELECT 1 FROM mapping_rapor ada
  WHERE ada.mapel_id = src.mapel_id AND ada.tingkat = '8' AND ada.kurikulum = src.kurikulum
);

INSERT INTO mapping_rapor (mapel_id, tampil_rapor, urutan, kurikulum, tingkat, nama_lokal, kelompok_id)
SELECT src.mapel_id, src.tampil_rapor, src.urutan, src.kurikulum, '9', src.nama_lokal, src.kelompok_id
FROM mapping_rapor src
WHERE src.tingkat = '7'
AND NOT EXISTS (
  SELECT 1 FROM mapping_rapor ada
  WHERE ada.mapel_id = src.mapel_id AND ada.tingkat = '9' AND ada.kurikulum = src.kurikulum
);

SET @ada_kode_dimensi := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'dimensi_sikap' AND COLUMN_NAME = 'kode'
);
SET @sql_kode_dimensi := IF(@ada_kode_dimensi = 0, 'ALTER TABLE dimensi_sikap ADD COLUMN kode VARCHAR(60) NULL', 'SELECT 1');
PREPARE stmt_kode_dimensi FROM @sql_kode_dimensi;
EXECUTE stmt_kode_dimensi;
DEALLOCATE PREPARE stmt_kode_dimensi;

UPDATE dimensi_sikap SET kode = 'keimanan' WHERE (kode IS NULL OR kode = '') AND nama LIKE 'Keimanan%';
UPDATE dimensi_sikap SET kode = 'penalaran' WHERE (kode IS NULL OR kode = '') AND nama LIKE 'Penalaran%';
UPDATE dimensi_sikap SET kode = 'kreativitas' WHERE (kode IS NULL OR kode = '') AND nama LIKE 'Kreativitas%';
UPDATE dimensi_sikap SET kode = 'gotong' WHERE (kode IS NULL OR kode = '') AND nama LIKE 'Gotong%';
UPDATE dimensi_sikap SET kode = CONCAT('dimensi-', id) WHERE kode IS NULL OR kode = '';

SET @ada_aspek_urutan := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'aspek_tahfiz' AND COLUMN_NAME = 'urutan'
);
SET @sql_aspek_urutan := IF(@ada_aspek_urutan = 0, 'ALTER TABLE aspek_tahfiz ADD COLUMN urutan INT NULL', 'SELECT 1');
PREPARE stmt_aspek_urutan FROM @sql_aspek_urutan;
EXECUTE stmt_aspek_urutan;
DEALLOCATE PREPARE stmt_aspek_urutan;

SET @ada_aspek_aktif := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'aspek_tahfiz' AND COLUMN_NAME = 'aktif'
);
SET @sql_aspek_aktif := IF(@ada_aspek_aktif = 0, 'ALTER TABLE aspek_tahfiz ADD COLUMN aktif TINYINT NOT NULL DEFAULT 1', 'SELECT 1');
PREPARE stmt_aspek_aktif FROM @sql_aspek_aktif;
EXECUTE stmt_aspek_aktif;
DEALLOCATE PREPARE stmt_aspek_aktif;

SET @ada_aspek_dibuat := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'aspek_tahfiz' AND COLUMN_NAME = 'dibuat'
);
SET @sql_aspek_dibuat := IF(@ada_aspek_dibuat = 0, 'ALTER TABLE aspek_tahfiz ADD COLUMN dibuat DATETIME NULL', 'SELECT 1');
PREPARE stmt_aspek_dibuat FROM @sql_aspek_dibuat;
EXECUTE stmt_aspek_dibuat;
DEALLOCATE PREPARE stmt_aspek_dibuat;

UPDATE aspek_tahfiz SET aktif = 1 WHERE aktif IS NULL;
UPDATE aspek_tahfiz SET dibuat = NOW() WHERE dibuat IS NULL;
UPDATE aspek_tahfiz a
JOIN (
  SELECT id, ROW_NUMBER() OVER (ORDER BY id) AS nomor FROM aspek_tahfiz
) x ON x.id = a.id
SET a.urutan = x.nomor
WHERE a.urutan IS NULL;

SET @ada_map_dibuat := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mapping_guru_tahfiz' AND COLUMN_NAME = 'dibuat'
);
SET @sql_map_dibuat := IF(@ada_map_dibuat = 0, 'ALTER TABLE mapping_guru_tahfiz ADD COLUMN dibuat DATETIME NULL', 'SELECT 1');
PREPARE stmt_map_dibuat FROM @sql_map_dibuat;
EXECUTE stmt_map_dibuat;
DEALLOCATE PREPARE stmt_map_dibuat;

UPDATE mapping_guru_tahfiz SET dibuat = NOW() WHERE dibuat IS NULL;

SET @ada_tgl_hijriah := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'pengaturan_rapor_tahfiz' AND COLUMN_NAME = 'tanggal_hijriah'
);
SET @sql_tgl_hijriah := IF(@ada_tgl_hijriah = 0, 'ALTER TABLE pengaturan_rapor_tahfiz ADD COLUMN tanggal_hijriah VARCHAR(80) NULL', 'SELECT 1');
PREPARE stmt_tgl_hijriah FROM @sql_tgl_hijriah;
EXECUTE stmt_tgl_hijriah;
DEALLOCATE PREPARE stmt_tgl_hijriah;

SET @ada_tgl_masehi := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'pengaturan_rapor_tahfiz' AND COLUMN_NAME = 'tanggal_masehi'
);
SET @sql_tgl_masehi := IF(@ada_tgl_masehi = 0, 'ALTER TABLE pengaturan_rapor_tahfiz ADD COLUMN tanggal_masehi VARCHAR(80) NULL', 'SELECT 1');
PREPARE stmt_tgl_masehi FROM @sql_tgl_masehi;
EXECUTE stmt_tgl_masehi;
DEALLOCATE PREPARE stmt_tgl_masehi;

SET @ada_tempat_cetak := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'pengaturan_rapor_tahfiz' AND COLUMN_NAME = 'tempat_cetak'
);
SET @sql_tempat_cetak := IF(@ada_tempat_cetak = 0, 'ALTER TABLE pengaturan_rapor_tahfiz ADD COLUMN tempat_cetak VARCHAR(120) NULL', 'SELECT 1');
PREPARE stmt_tempat_cetak FROM @sql_tempat_cetak;
EXECUTE stmt_tempat_cetak;
DEALLOCATE PREPARE stmt_tempat_cetak;

SET @ada_nama_kepala_tahfiz := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'pengaturan_rapor_tahfiz' AND COLUMN_NAME = 'nama_kepala'
);
SET @sql_nama_kepala_tahfiz := IF(@ada_nama_kepala_tahfiz = 0, 'ALTER TABLE pengaturan_rapor_tahfiz ADD COLUMN nama_kepala VARCHAR(150) NULL', 'SELECT 1');
PREPARE stmt_nama_kepala_tahfiz FROM @sql_nama_kepala_tahfiz;
EXECUTE stmt_nama_kepala_tahfiz;
DEALLOCATE PREPARE stmt_nama_kepala_tahfiz;

SET @ada_nbm_tahfiz := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'pengaturan_rapor_tahfiz' AND COLUMN_NAME = 'nbm_kepala'
);
SET @sql_nbm_tahfiz := IF(@ada_nbm_tahfiz = 0, 'ALTER TABLE pengaturan_rapor_tahfiz ADD COLUMN nbm_kepala VARCHAR(40) NULL', 'SELECT 1');
PREPARE stmt_nbm_tahfiz FROM @sql_nbm_tahfiz;
EXECUTE stmt_nbm_tahfiz;
DEALLOCATE PREPARE stmt_nbm_tahfiz;
