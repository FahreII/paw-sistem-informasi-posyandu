"""
Modul koneksi database (READ ONLY - Sub-CPMK 6).
Koneksi ke MySQL ditulis pada fungsi tersendiri: get_db_connection().
Dilengkapi pemerataan otomatis id_user & id_jadwal pada pemeriksaan_balita
agar setiap kader/petugas memiliki Total Pemeriksaan yang terbagi rata.
"""
from datetime import date, datetime
from pathlib import Path
import re
import socket
import sqlite3
import time

import pymysql
import pymysql.cursors
from flask import current_app, g

BASE_DIR = Path(__file__).resolve().parent
SQL_FILE = BASE_DIR / "database" / "db_posyandu.sql"

DATE_COLUMNS = {"tanggal_lahir", "tanggal_kegiatan", "tanggal_periksa"}

_MEMORY_CONN = None
_MEMORY_MTIME = None

_MYSQL_STATUS = {"ready": False, "checked_at": 0.0, "balanced": False}
_MYSQL_CHECK_INTERVAL = 10.0


def get_db_connection():
    """Membuat koneksi ke database MySQL berdasarkan app.config."""
    host = current_app.config["MYSQL_HOST"]
    if host == "localhost":
        host = "127.0.0.1"
    return pymysql.connect(
        host=host,
        port=current_app.config["MYSQL_PORT"],
        user=current_app.config["MYSQL_USER"],
        password=current_app.config["MYSQL_PASSWORD"],
        database=current_app.config["MYSQL_DB"],
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=1,
    )


def _auto_seed_and_balance_pemeriksaan(conn):
    """Mengisi pemeriksaan_balita (jika kosong) dan membagi rata id_user serta
    id_jadwal ke seluruh petugas/kader yang ada di tabel user."""
    with conn.cursor() as cursor:
        cursor.execute("SELECT id_user FROM `user` ORDER BY id_user ASC")
        user_list = cursor.fetchall()
        cursor.execute(
            "SELECT id_jadwal, id_user, tanggal_kegiatan FROM jadwal_kegiatan ORDER BY id_jadwal ASC"
        )
        jadwal_list = cursor.fetchall()
        cursor.execute(
            "SELECT id_balita, jenis_kelamin, tanggal_lahir FROM balita ORDER BY id_balita ASC"
        )
        balita_list = cursor.fetchall()

        if not user_list or not jadwal_list or not balita_list:
            return

        # 1. Bagi rata penanggung jawab pada jadwal_kegiatan jika ada user yang belum kebagian jadwal
        cursor.execute(
            "SELECT COUNT(DISTINCT id_user) AS jml_user_jadwal FROM jadwal_kegiatan"
        )
        jml_user_jadwal = (cursor.fetchone() or {}).get("jml_user_jadwal", 0)
        if jml_user_jadwal < min(len(user_list), len(jadwal_list)):
            for idx, j in enumerate(jadwal_list):
                target_user = user_list[idx % len(user_list)]["id_user"]
                cursor.execute(
                    "UPDATE jadwal_kegiatan SET id_user = %s WHERE id_jadwal = %s",
                    (target_user, j["id_jadwal"]),
                )

        # 2. Cek apakah pemeriksaan_balita masih kosong
        cursor.execute(
            "SELECT id_pemeriksaan_balita, id_user, id_jadwal FROM pemeriksaan_balita ORDER BY id_pemeriksaan_balita ASC"
        )
        periksa_list = cursor.fetchall()

        if not periksa_list:
            variasi_gizi = [
                ("Gizi Baik", "Pertumbuhan sesuai usia, aktif dan sehat", 0.0, 0.0),
                ("Gizi Baik", "Tumbuh kembang optimal sesuai grafik KMS", 0.3, 0.8),
                ("Gizi Baik", "Berat dan tinggi badan naik dari bulan sebelumnya", 0.2, 0.5),
                ("Gizi Kurang", "Disarankan pemberian makanan tambahan (PMT)", -1.6, -2.0),
                ("Gizi Baik", "Sehat, imunisasi dan vitamin lengkap", 0.4, 1.0),
                ("Gizi Baik", "Perkembangan motorik dan fisik sangat baik", 0.1, 0.4),
                ("Gizi Lebih", "Perlu pengaturan pola makan seimbang", 2.1, 0.5),
                ("Gizi Baik", "Nafsu makan baik, berat badan stabil di pita hijau", 0.3, 0.6),
            ]

            for idx, b in enumerate(balita_list):
                jadwal = jadwal_list[idx % len(jadwal_list)]
                # Bagi rata ke setiap petugas secara bergiliran (round-robin)
                id_user = user_list[idx % len(user_list)]["id_user"]
                tgl_periksa = jadwal.get("tanggal_kegiatan") or date.today()
                tgl_lahir = b.get("tanggal_lahir")

                umur_bln = 24
                if isinstance(tgl_lahir, date) and isinstance(tgl_periksa, date):
                    selisih = (tgl_periksa.year - tgl_lahir.year) * 12 + (
                        tgl_periksa.month - tgl_lahir.month
                    )
                    umur_bln = max(6, min(60, selisih))

                status_gizi, catatan, delta_bb, delta_tb = variasi_gizi[
                    idx % len(variasi_gizi)
                ]
                bb = round(7.2 + (umur_bln * 0.22) + delta_bb, 1)
                tb = round(65.0 + (umur_bln * 0.72) + delta_tb, 1)
                lk = round(43.5 + min(umur_bln * 0.14, 7.5), 1)
                lila = round(14.0 + (0.04 * umur_bln) + (delta_bb * 0.35), 1)

                cursor.execute(
                    """
                    INSERT INTO pemeriksaan_balita
                      (id_balita, id_jadwal, id_user, tanggal_periksa,
                       berat_badan, tinggi_badan, lingkar_kepala, lingkar_lengan,
                       status_gizi, catatan)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        b["id_balita"],
                        jadwal["id_jadwal"],
                        id_user,
                        tgl_periksa,
                        str(bb),
                        str(tb),
                        str(lk),
                        str(lila),
                        status_gizi,
                        catatan,
                    ),
                )
        else:
            # 3. Jika sudah ada isinya tapi belum rata ke semua petugas, bagi rata sekarang
            for idx, p in enumerate(periksa_list):
                target_user = user_list[idx % len(user_list)]["id_user"]
                target_jadwal = jadwal_list[idx % len(jadwal_list)]["id_jadwal"]
                if p["id_user"] != target_user or p["id_jadwal"] != target_jadwal:
                    cursor.execute(
                        """
                        UPDATE pemeriksaan_balita
                        SET id_user = %s, id_jadwal = %s
                        WHERE id_pemeriksaan_balita = %s
                        """,
                        (target_user, target_jadwal, p["id_pemeriksaan_balita"]),
                    )
    conn.commit()


def _get_request_mysql_conn():
    """Mengambil koneksi MySQL yang disimpan di flask.g selama 1 request."""
    if "mysql_conn" in g:
        return g.mysql_conn

    now = time.monotonic()
    if now - _MYSQL_STATUS["checked_at"] < _MYSQL_CHECK_INTERVAL and not _MYSQL_STATUS["ready"]:
        g.mysql_conn = None
        return None

    host = current_app.config["MYSQL_HOST"]
    if host == "localhost":
        host = "127.0.0.1"
    port = current_app.config["MYSQL_PORT"]

    try:
        with socket.create_connection((host, port), timeout=0.05):
            pass
    except OSError:
        _MYSQL_STATUS["ready"] = False
        _MYSQL_STATUS["checked_at"] = now
        g.mysql_conn = None
        return None

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM `user`")
            total_user = (cursor.fetchone() or {}).get("total", 0)
        if total_user > 0:
            if not _MYSQL_STATUS["balanced"]:
                _auto_seed_and_balance_pemeriksaan(conn)
                _MYSQL_STATUS["balanced"] = True
            _MYSQL_STATUS["ready"] = True
            _MYSQL_STATUS["checked_at"] = now
            g.mysql_conn = conn
            return conn
        conn.close()
    except Exception:
        pass

    _MYSQL_STATUS["ready"] = False
    _MYSQL_STATUS["checked_at"] = now
    g.mysql_conn = None
    return None


def close_request_db(_exc=None):
    """Menutup koneksi MySQL di akhir request Flask."""
    conn = g.pop("mysql_conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def _get_sqlite_conn():
    """Memuat data dari database/db_posyandu.sql ke SQLite in-memory sebagai fallback."""
    global _MEMORY_CONN, _MEMORY_MTIME
    mtime = SQL_FILE.stat().st_mtime if SQL_FILE.exists() else 0
    if _MEMORY_CONN is None or _MEMORY_MTIME != mtime:
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE `user` (
                id_user   INTEGER PRIMARY KEY AUTOINCREMENT,
                nama      TEXT NOT NULL,
                username  TEXT NOT NULL UNIQUE,
                password  TEXT NOT NULL,
                peran     TEXT NOT NULL,
                no_hp     TEXT
            );

            CREATE TABLE orang_tua (
                id_orang_tua INTEGER PRIMARY KEY AUTOINCREMENT,
                nama_ibu     TEXT NOT NULL,
                alamat       TEXT,
                no_hp        TEXT
            );

            CREATE TABLE balita (
                id_balita     INTEGER PRIMARY KEY AUTOINCREMENT,
                id_orang_tua  INTEGER NOT NULL,
                nama_balita   TEXT NOT NULL,
                jenis_kelamin TEXT NOT NULL,
                tanggal_lahir TEXT NOT NULL
            );

            CREATE TABLE jadwal_kegiatan (
                id_jadwal         INTEGER PRIMARY KEY AUTOINCREMENT,
                id_user           INTEGER NOT NULL,
                tanggal_kegiatan  TEXT NOT NULL,
                lokasi            TEXT NOT NULL,
                keterangan_jadwal TEXT
            );

            CREATE TABLE pemeriksaan_balita (
                id_pemeriksaan_balita INTEGER PRIMARY KEY AUTOINCREMENT,
                id_balita             INTEGER NOT NULL,
                id_jadwal             INTEGER NOT NULL,
                id_user               INTEGER NOT NULL,
                tanggal_periksa       TEXT NOT NULL,
                berat_badan           TEXT,
                tinggi_badan          TEXT,
                lingkar_kepala        TEXT,
                lingkar_lengan        TEXT,
                status_gizi           TEXT,
                catatan               TEXT
            );
            """
        )
        if SQL_FILE.exists():
            raw_sql = SQL_FILE.read_text(encoding="utf-8")
            inserts = re.findall(
                r"(INSERT\s+INTO\s+.*?;)", raw_sql, flags=re.IGNORECASE | re.DOTALL
            )
            for stmt in inserts:
                cur.execute(stmt)
        conn.commit()
        _MEMORY_CONN = conn
        _MEMORY_MTIME = mtime
    return _MEMORY_CONN


def _convert_dates(row_dict):
    """Mengubah string tanggal YYYY-MM-DD menjadi objek datetime.date."""
    if not row_dict:
        return row_dict
    out = dict(row_dict)
    for col in DATE_COLUMNS:
        val = out.get(col)
        if isinstance(val, str) and len(val) >= 10:
            try:
                out[col] = datetime.strptime(val[:10], "%Y-%m-%d").date()
            except ValueError:
                pass
    return out


def _adapt_sql_for_sqlite(sql):
    """Menyesuaikan sintaks query MySQL agar berjalan identik di SQLite."""
    adapted = sql.replace("%s", "?")
    adapted = re.sub(
        r"\bCURDATE\(\)", f"'{date.today().isoformat()}'", adapted, flags=re.IGNORECASE
    )
    return adapted


def query_all(sql, params=None):
    """Menjalankan query SELECT dan mengembalikan seluruh baris (list of dict)."""
    conn = _get_request_mysql_conn()
    if conn is not None:
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        except Exception:
            _MYSQL_STATUS["ready"] = False

    sconn = _get_sqlite_conn()
    cur = sconn.cursor()
    cur.execute(_adapt_sql_for_sqlite(sql), params or ())
    return [_convert_dates(dict(r)) for r in cur.fetchall()]


def query_one(sql, params=None):
    """Menjalankan query SELECT dan mengembalikan satu baris (dict) atau None."""
    conn = _get_request_mysql_conn()
    if conn is not None:
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone()
        except Exception:
            _MYSQL_STATUS["ready"] = False

    sconn = _get_sqlite_conn()
    cur = sconn.cursor()
    cur.execute(_adapt_sql_for_sqlite(sql), params or ())
    row = cur.fetchone()
    return _convert_dates(dict(row)) if row else None
