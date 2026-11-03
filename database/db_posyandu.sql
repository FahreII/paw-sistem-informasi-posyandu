-- =========================================================
-- Database  : db_posyandu
-- Topik     : Sistem Informasi Posyandu Balita
-- Keterangan: Skrip pembuatan struktur tabel.
--             Data awal (minimal 20 baris per tabel) diisi
--             sendiri oleh kelompok di bagian bawah file ini.
-- =========================================================

CREATE DATABASE IF NOT EXISTS db_posyandu;
USE db_posyandu;

-- Hapus tabel lama (urutan dari tabel anak ke induk)
DROP TABLE IF EXISTS pemeriksaan_balita;
DROP TABLE IF EXISTS jadwal_kegiatan;
DROP TABLE IF EXISTS balita;
DROP TABLE IF EXISTS orang_tua;
DROP TABLE IF EXISTS `user`;

-- ---------------------------------------------------------
-- Tabel: user (petugas / kader posyandu)
-- ---------------------------------------------------------
CREATE TABLE `user` (
    id_user   INT          NOT NULL AUTO_INCREMENT,
    nama      VARCHAR(100) NOT NULL,
    username  VARCHAR(50)  NOT NULL UNIQUE,
    password  VARCHAR(255) NOT NULL,
    peran     VARCHAR(100) NOT NULL,
    no_hp     VARCHAR(15),
    PRIMARY KEY (id_user)
) ENGINE=InnoDB;

-- ---------------------------------------------------------
-- Tabel: orang_tua
-- ---------------------------------------------------------
CREATE TABLE orang_tua (
    id_orang_tua INT          NOT NULL AUTO_INCREMENT,
    nama_ibu     VARCHAR(50)  NOT NULL,
    alamat       VARCHAR(100),
    no_hp        VARCHAR(15),
    PRIMARY KEY (id_orang_tua)
) ENGINE=InnoDB;

-- ---------------------------------------------------------
-- Tabel: balita
-- ---------------------------------------------------------
CREATE TABLE balita (
    id_balita     INT          NOT NULL AUTO_INCREMENT,
    id_orang_tua  INT          NOT NULL,
    nama_balita   VARCHAR(100) NOT NULL,
    jenis_kelamin ENUM('Laki-laki', 'Perempuan') NOT NULL,
    tanggal_lahir DATE         NOT NULL,
    PRIMARY KEY (id_balita),
    FOREIGN KEY (id_orang_tua) REFERENCES orang_tua (id_orang_tua)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------
-- Tabel: jadwal_kegiatan
-- ---------------------------------------------------------
CREATE TABLE jadwal_kegiatan (
    id_jadwal         INT          NOT NULL AUTO_INCREMENT,
    id_user           INT          NOT NULL,
    tanggal_kegiatan  DATE         NOT NULL,
    lokasi            VARCHAR(100) NOT NULL,
    keterangan_jadwal VARCHAR(30),
    PRIMARY KEY (id_jadwal),
    FOREIGN KEY (id_user) REFERENCES `user` (id_user)
        ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------
-- Tabel: pemeriksaan_balita
-- ---------------------------------------------------------
CREATE TABLE pemeriksaan_balita (
    id_pemeriksaan_balita INT          NOT NULL AUTO_INCREMENT,
    id_balita             INT          NOT NULL,
    id_jadwal             INT          NOT NULL,
    id_user               INT          NOT NULL,
    tanggal_periksa       DATE         NOT NULL,
    berat_badan           VARCHAR(30),
    tinggi_badan          VARCHAR(30),
    lingkar_kepala        VARCHAR(30),
    lingkar_lengan        VARCHAR(30),
    status_gizi           VARCHAR(30),
    catatan               VARCHAR(255),
    PRIMARY KEY (id_pemeriksaan_balita),
    FOREIGN KEY (id_balita) REFERENCES balita (id_balita)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (id_jadwal) REFERENCES jadwal_kegiatan (id_jadwal)
        ON UPDATE CASCADE,
    FOREIGN KEY (id_user) REFERENCES `user` (id_user)
        ON UPDATE CASCADE
) ENGINE=InnoDB;


-- =========================================================
-- DATA AWAL (5 data per tabel)
-- WAJIB diisi berurutan: user -> orang_tua -> balita
--                        -> jadwal_kegiatan -> pemeriksaan_balita
-- =========================================================

-- 1) user (petugas / kader)
INSERT INTO `user` (nama, username, password, peran, no_hp) VALUES
('Asfiaaul Auliaa', 'Aul', 'asfiaul123', 'Kader', '082327373005'),
('Abitien Ahmad Fahrel', 'Fahrel', 'crazykiller231', 'Kader', '082317945481'),
('Rian Adriansyah', 'Rian', 'rian2414', 'Ketua Kader', '082158056138'),
('Vivi Lutfiah', 'Vivi', 'vivi1216', 'Kader', '081320131963'),
('Fauzan Nafis', 'Fauzan', 'mimir', 'Kader', '082120159637');

-- 2) orang_tua
INSERT INTO orang_tua (nama_ibu, alamat, no_hp) VALUES
('Rina Marlina', 'Jl. Melati No. 12 RT 01/RW 02', '085711110001'),
('Yuni Kartika', 'Jl. Mawar No. 5 RT 02/RW 02', '085711110002'),
('Dewi Anggraini', 'Jl. Kenanga No. 8 RT 03/RW 02', '085711110003'),
('Sri Wahyuni', 'Jl. Dahlia No. 19 RT 01/RW 03', '085711110004'),
('Nadia Kusuma', 'Jl. Anggrek No. 3 RT 04/RW 03', '085711110005');

-- 3) balita (id_orang_tua 1 s/d 5)
INSERT INTO balita (id_orang_tua, nama_balita, jenis_kelamin, tanggal_lahir) VALUES
(1, 'Ahmad Rafa', 'Laki-laki', '2023-03-14'),
(2, 'Nabila Putri', 'Perempuan', '2022-11-02'),
(3, 'Bagas Pratama', 'Laki-laki', '2024-01-20'),
(4, 'Aisyah Zahra', 'Perempuan', '2023-07-08'),
(5, 'Dimas Putra', 'Laki-laki', '2024-05-16');

-- 4) jadwal_kegiatan (id_user 1 s/d 5)
INSERT INTO jadwal_kegiatan (id_user, tanggal_kegiatan, lokasi, keterangan_jadwal) VALUES
(1, '2026-09-10', 'Posyandu Melati RW 02', 'Penimbangan rutin'),
(2, '2026-10-10', 'Posyandu Melati RW 02', 'Imunisasi & vitamin A'),
(3, '2026-11-01', 'Posyandu Mawar RW 03', 'Pemeriksaan tumbuh kembang'),
(4, '2026-11-15', 'Posyandu Melati RW 02', 'Pemberian makanan tambahan'),
(5, '2026-12-10', 'Posyandu Mawar RW 03', 'Penyuluhan gizi balita');

-- 5) pemeriksaan_balita (untuk 5 balita oleh 5 petugas)
INSERT INTO pemeriksaan_balita
  (id_balita, id_jadwal, id_user, tanggal_periksa, berat_badan, tinggi_badan,
   lingkar_kepala, lingkar_lengan, status_gizi, catatan) VALUES
(1, 1, 1, '2026-09-10', '13.8', '96.5', '49.5', '16.0', 'Gizi Baik', 'Pertumbuhan sesuai usia, aktif dan sehat'),
(2, 1, 2, '2026-09-10', '14.2', '99.0', '49.8', '16.2', 'Gizi Baik', 'Tumbuh kembang optimal'),
(3, 2, 3, '2026-10-10', '10.4', '88.0', '47.5', '13.8', 'Gizi Kurang', 'Disarankan pemberian makanan tambahan (PMT)'),
(4, 2, 4, '2026-10-10', '13.1', '94.0', '48.6', '15.5', 'Gizi Baik', 'Berat badan naik dari bulan sebelumnya'),
(5, 3, 5, '2026-11-01', '14.5', '90.0', '48.9', '17.4', 'Gizi Lebih', 'Perlu pengaturan pola makan seimbang');
