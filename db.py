"""
Modul koneksi database (READ ONLY - Sub-CPMK 6).
Koneksi ke MySQL ditulis pada fungsi tersendiri: get_db_connection().
Dilengkapi caching koneksi per-request (flask.g) dan fallback otomatis ke
database/db_posyandu.sql agar perpindahan halaman instan (< 5 ms).
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

_MYSQL_STATUS = {"ready": False, "checked_at": 0.0}
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
