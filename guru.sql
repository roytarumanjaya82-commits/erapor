-- Data guru eRapor SMPM22SETIABUDIPAMULANG
-- Sumber: Jadwal Pelajaran 2026-2027
-- Menjalankan file ini mengganti seluruh isi tabel guru.
-- Pembelajaran yang masih menempel pada guru lama ikut terhapus.
USE erapor_smamduma;

ALTER TABLE guru MODIFY gelar_belakang VARCHAR(80) DEFAULT '';
ALTER TABLE guru MODIFY jenis_kelamin ENUM('L','P') NULL;

SET @ada_mapel := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'guru' AND COLUMN_NAME = 'mapel_ajar'
);
SET @sql_mapel := IF(@ada_mapel = 0, 'ALTER TABLE guru ADD COLUMN mapel_ajar TEXT NULL', 'SELECT 1');
PREPARE stmt_mapel FROM @sql_mapel;
EXECUTE stmt_mapel;
DEALLOCATE PREPARE stmt_mapel;

SET @ada_jam := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'guru' AND COLUMN_NAME = 'jumlah_jam'
);
SET @sql_jam := IF(@ada_jam = 0, 'ALTER TABLE guru ADD COLUMN jumlah_jam INT NULL', 'SELECT 1');
PREPARE stmt_jam FROM @sql_jam;
EXECUTE stmt_jam;
DEALLOCATE PREPARE stmt_jam;

SET @ada_kelas := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'guru' AND COLUMN_NAME = 'mengajar_di'
);
SET @sql_kelas := IF(@ada_kelas = 0, 'ALTER TABLE guru ADD COLUMN mengajar_di TEXT NULL', 'SELECT 1');
PREPARE stmt_kelas FROM @sql_kelas;
EXECUTE stmt_kelas;
DEALLOCATE PREPARE stmt_kelas;

DELETE FROM guru;

INSERT INTO guru (nama, gelar_depan, gelar_belakang, jenis_kelamin, status_kepegawaian, mapel_ajar, jumlah_jam, mengajar_di, aktif) VALUES
('Ikhsan Saepul Munir', '', 'S.Pd.', NULL, 'Guru', '', 0, '', 1),
('Yunus Anis', '', 'M.Pd.', NULL, 'Guru', 'Al Islam (29)', 29, '8.1. 8.2, 8.3, 8.4, 8.5, 9.5', 1),
('Roni Boan Elarika', '', 'M. Pd.', NULL, 'Guru', 'Bahasa Indonesia (35)', 35, '7.1, 7.2, 8.4, 8.5, 9.1, 9.2', 1),
('Indratni Khair', '', 'S.Ag.', NULL, 'Guru', 'Al Islam (33)', 33, 'F', 1),
('Rohidah', '', 'S. Pd.', NULL, 'Guru', 'Bhs. Inggris (7)', 7, '8.2, 8.3', 1),
('Susilistari', '', 'SE.', NULL, 'Guru', 'IPS Terpadu (32)', 32, '7.1- 7.6, 8.1, 8.2', 1),
('Roy Tarumanjaya', '', 'S.Kom.', NULL, 'Guru', 'Informatika (26), Koding (4)', 30, '7.1 - 7.6, 8.4, 8.5, 9.1 - 9.5; 7.5, 8.5', 1),
('Mulyadi Hikmah', '', 'S.Kom.', NULL, 'Guru', 'PJOK (32)', 32, '7.1 - 7.6, 8.1 - 8.5, 9.1 - 9.5', 1),
('Deny Asmara', '', 'S.Pd.', NULL, 'Guru', 'Bahasa Indonesia (22)', 22, '8.3, 9.3, 9.4, 9.5', 1),
('Maryono', '', 'S.Pd.', NULL, 'Guru', 'Bahasa Inggris (29)', 29, '7.5, 8.4, 8.5 & 9.1 - 9.5', 1),
('Rina Herliani', '', 'S.Pd.', NULL, 'Guru', 'IPA Terpadu (34)', 34, '7.1, 7.2, 9.1 - 9.5', 1),
('Faizal Haizar', '', 'S.H.I.', NULL, 'Guru', 'Al Islam (15)', 15, '9.1, 9.2, 9.4', 1),
('Eda Nurhaedah', '', 'S.Pd.', NULL, 'Guru', 'Matematika (28)', 28, '8.1, 8.2, 8.3, 8.4, 8.5, 9.5', 1),
('Ilham', '', '', NULL, 'Guru', 'Tapak Suci (32)', 32, '7.1 - 7.6, 8.1 - 8.5, 9.1 - 9.5', 1),
('Faizah Adisty', '', 'M.Pd.', NULL, 'Guru', 'Matematika (33)', 33, '7.4 -7.6, 9.1 - 9.4', 1),
('Jamsiyah', '', 'S.Pd.', NULL, 'Guru', 'PPKn (28)', 28, '7.1, 7.2, 7.3, 7.6, 8.1 - 8.5, 9.1 - 9.5', 1),
('Nurul Mizani', '', 'S.Pd.', NULL, 'Guru', 'Bahasa Indonesia (34)', 34, '7.3, 7.4, 7.5, 7.6, 8.1, 8.2', 1),
('Ade Julia Safitri', '', 'S.Pd.I', NULL, 'Guru', 'Bahasa Arab (32)', 32, '7.1 - 7.6, 8.1 - 8.5, 9.1 - 9.5', 1),
('Bhisma Satria Pamungkas', '', 'S.P.', NULL, 'Guru', 'Seni Budaya (32)', 32, '7.1 - 7.6, 8.1 - 8.5, 9.1 - 9.5', 1),
('Mauliza Ahmad', '', 'S.Pd', NULL, 'Guru', 'IPA Terpadu (31)', 31, '7.3 - 7.5, 8.2 - 8.5', 1),
('Agita Daimon', '', 'S.Pd.', NULL, 'Guru', 'Kemuhammadiyahan (29)', 29, '7.1 - 7.6, 8.1 - 8.5, 9.1 - 9.5', 1),
('Alriefan Rachmadi', '', 'S.Pd.', NULL, 'Guru', 'IPS Terpadu (32)', 32, '8.3 - 8.5, 9.1 - 9.5', 1),
('Sa`diah Sari Hasanah', '', 'S.Pd.', NULL, 'Guru', 'BK', 0, '8.3 - 8.5, 9.1 - 9.5', 1),
('Nelsa Nurul Hamidah', '', 'S.Pd.', NULL, 'Guru', 'BK', 0, '7.1 - 7.6 & 8.1, 8.2', 1),
('Agus Salim', '', 'M.Pd.', NULL, 'Guru', 'Tahfidz (24)', 24, '7.3, 8.3, 9.3', 1),
('Hermanida', '', 'S.Pd.', NULL, 'Guru', 'Tahfidz (24)', 24, '7.3, 8.3, 9.3', 1),
('Yoga Parenta', '', 'M.Pd.', NULL, 'Guru', 'IPA Terpadu (10), Matematika (14)', 24, '7.6, 8.1; 7.1, 7.2, 7.3', 1),
('Susilo M', '', 'Amd.Kom', NULL, 'Guru', 'Informatika (6), Koding (10), Desain Grafis (4), Broadcasting (4)', 24, '8.1, 8.2, 8.3; 7.1, 7.2, 7.3, 7.4, 7.6; 7.5, 8.5', 1),
('Meutia Khanza', '', 'M.Pd.', NULL, 'Guru', 'Bahasa Inggris (23)', 23, '7.1, 7.2, 7.3, 7.4, 7.6, 8.1', 1),
('Muhammad Sofyan', '', '', NULL, 'Guru', 'PPKn (4)', 4, '7.4, 7.5', 1);
