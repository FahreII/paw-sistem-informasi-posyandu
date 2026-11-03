"""
Konfigurasi dasar aplikasi Posyandu Balita.
Semua pengaturan dimuat ke Flask melalui app.config.from_object(Config).
"""


class Config:
    # Mode debug untuk tahap pengembangan (matikan saat production)
    DEBUG = True

    # Kunci rahasia aplikasi (dipakai untuk session / form)
    SECRET_KEY = "ganti-dengan-kunci-rahasia-kelompok"

    # Nama aplikasi (ditampilkan di navbar & judul halaman)
    APP_NAME = "Posyandu Balita"

    # Pengaturan koneksi database MySQL (XAMPP)
    MYSQL_HOST = "127.0.0.1"
    MYSQL_PORT = 3306
    MYSQL_USER = "root"
    MYSQL_PASSWORD = ""          # default XAMPP: kosong
    MYSQL_DB = "db_posyandu"
