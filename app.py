"""
Aplikasi Web Sistem Informasi Posyandu & Pemantauan Stunting Balita
Tugas Praktikum Pengembangan Aplikasi Web (Flask)

Tahap 1 : instalasi, konfigurasi, route, template Jinja2, static CSS
Tahap 2 : menampilkan data dari database (READ: daftar, detail, pencarian & filter)
"""
from datetime import date

import pymysql
from flask import Flask, abort, render_template, request

from config import Config
from db import close_request_db, query_all, query_one

# ---------------------------------------------------------------------------
# Inisialisasi & konfigurasi aplikasi (app.config)
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config.from_object(Config)
app.teardown_appcontext(close_request_db)

# Menu navigasi utama
MENU = [
    {"key": "beranda", "endpoint": "beranda", "label": "Posyandu"},
    {"key": "balita", "endpoint": "daftar_balita", "label": "Pendataan Balita"},
    {"key": "orang_tua", "endpoint": "daftar_orang_tua", "label": "Orang Tua (KIA)"},
    {"key": "pemeriksaan", "endpoint": "daftar_pemeriksaan", "label": "Pemantauan Gizi"},
    {"key": "jadwal", "endpoint": "daftar_jadwal", "label": "Jadwal & Vaksin"},
    {"key": "petugas", "endpoint": "daftar_petugas", "label": "Petugas / Kader"},
    {"key": "scorecard", "endpoint": "scorecard", "label": "Scorecard Konvergensi"},
    {"key": "tentang", "endpoint": "tentang", "label": "Tentang"},
]

# Data 5 anggota kelompok sesuai data user di modulPAW
ANGGOTA_KELOMPOK = [
    {"nama": "Asfiaaul Auliaa", "peran": "Ketua Kader", "no_hp": "082327373005"},
    {"nama": "Abitien Ahmad Fahrel", "peran": "Kader", "no_hp": "082317945481"},
    {"nama": "Rian Adriansyah", "peran": "Kader", "no_hp": "082158056138"},
    {"nama": "Vivi Lutfiah", "peran": "Kader", "no_hp": "081320131963"},
    {"nama": "Fauzan Nafis", "peran": "Kader", "no_hp": "082120159637"},
]

NAMA_BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def ambil_statistik():
    """Mengambil ringkasan jumlah data dari kelima tabel untuk 4 kartu atas."""
    try:
        stat = query_one(
            """
            SELECT
                (SELECT COUNT(*) FROM balita)             AS balita,
                (SELECT COUNT(*) FROM orang_tua)          AS orang_tua,
                (SELECT COUNT(*) FROM pemeriksaan_balita) AS pemeriksaan,
                (SELECT COUNT(*) FROM jadwal_kegiatan)    AS jadwal,
                (SELECT COUNT(*) FROM `user`)             AS petugas,
                (SELECT COUNT(*) FROM pemeriksaan_balita
                 WHERE LOWER(status_gizi) LIKE '%baik%')  AS gizi_baik,
                (SELECT COUNT(*) FROM pemeriksaan_balita
                 WHERE LOWER(status_gizi) NOT LIKE '%baik%') AS perlu_pantau
            """
        )
        if stat:
            return stat
    except Exception:
        pass
    return {
        "balita": 0,
        "orang_tua": 0,
        "pemeriksaan": 0,
        "jadwal": 0,
        "petugas": 0,
        "gizi_baik": 0,
        "perlu_pantau": 0,
    }


@app.context_processor
def inject_global():
    """Variabel yang otomatis tersedia di semua template."""
    return {
        "menu": MENU,
        "tahun_ini": date.today().year,
        "stats_global": ambil_statistik(),
    }


# ---------------------------------------------------------------------------
# Filter Jinja2 kustom
# ---------------------------------------------------------------------------
@app.template_filter("tanggal")
def format_tanggal(value):
    """Mengubah objek date menjadi format '17 Agustus 2024'."""
    if not value:
        return "-"
    if isinstance(value, str):
        return value
    return f"{value.day} {NAMA_BULAN[value.month - 1]} {value.year}"


def _umur_bulan(tanggal_lahir):
    if not tanggal_lahir or isinstance(tanggal_lahir, str):
        return None
    hari_ini = date.today()
    bulan = (hari_ini.year - tanggal_lahir.year) * 12 + (hari_ini.month - tanggal_lahir.month)
    if hari_ini.day < tanggal_lahir.day:
        bulan -= 1
    return max(bulan, 0)


@app.template_filter("umur")
def hitung_umur(tanggal_lahir):
    """Menghitung umur balita dari tanggal lahir (tahun & bulan)."""
    bulan = _umur_bulan(tanggal_lahir)
    if bulan is None:
        return "-"
    tahun, sisa_bulan = divmod(bulan, 12)
    if tahun == 0:
        return f"{sisa_bulan} bulan"
    return f"{tahun} thn {sisa_bulan} bln"


@app.template_filter("warna_gizi")
def warna_status_gizi(status):
    """Menentukan warna badge Bootstrap berdasarkan status gizi."""
    status = (status or "").lower()
    if "buruk" in status:
        return "danger"
    if "kurang" in status or "stunting" in status:
        return "warning"
    if "lebih" in status or "obesitas" in status:
        return "info"
    if "baik" in status or "normal" in status:
        return "success"
    return "secondary"


# ---------------------------------------------------------------------------
# TAHAP 1 : Route dasar & Dashboard utama (Stunting Posyandu)
# ---------------------------------------------------------------------------
@app.route("/")
def beranda():
    """Dashboard utama: menampilkan daftar Posyandu & kegiatan."""
    q = request.args.get("q", "").strip()

    sql = """
        SELECT j.id_jadwal, j.tanggal_kegiatan, j.lokasi, j.keterangan_jadwal,
               u.nama AS nama_petugas, u.no_hp AS hp_petugas
        FROM jadwal_kegiatan j
        LEFT JOIN `user` u ON j.id_user = u.id_user
        WHERE 1 = 1
    """
    params = []
    if q:
        sql += " AND (j.lokasi LIKE %s OR j.keterangan_jadwal LIKE %s OR u.nama LIKE %s)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    sql += " ORDER BY j.id_jadwal ASC"

    daftar_posyandu = query_all(sql, params)
    return render_template(
        "index.html",
        data=daftar_posyandu,
        q=q,
        active_sub="posyandu",
    )


@app.route("/tentang")
def tentang():
    """Halaman tentang aplikasi & anggota kelompok."""
    fitur = [
        "Dashboard Pemantauan Stunting & Posyandu terintegrasi",
        "Menampilkan daftar & detail data Balita beserta perhitungan umur otomatis",
        "Menampilkan daftar & detail Orang Tua / Ibu (KIA)",
        "Menampilkan daftar & detail Pemeriksaan Gizi (BB, TB, LK, LiLA, Status Gizi)",
        "Menampilkan daftar & detail Jadwal Kegiatan serta Kader Posyandu",
        "Fitur pencarian kata kunci dan filter kelompok usia / status gizi",
    ]
    petugas_db = query_all("SELECT id_user, nama, username, peran, no_hp FROM `user` ORDER BY id_user ASC")
    return render_template(
        "tentang.html",
        fitur=fitur,
        anggota=petugas_db or ANGGOTA_KELOMPOK,
        active_sub="tentang",
    )


@app.route("/scorecard")
def scorecard():
    """Halaman Scorecard Konvergensi Stunting & Rekapitulasi Gizi Posyandu."""
    rekap_periksa = query_all(
        """
        SELECT p.*, b.nama_balita, b.jenis_kelamin, b.tanggal_lahir,
               o.nama_ibu, o.alamat, u.nama AS nama_petugas, j.lokasi
        FROM pemeriksaan_balita p
        LEFT JOIN balita b          ON p.id_balita = b.id_balita
        LEFT JOIN orang_tua o       ON b.id_orang_tua = o.id_orang_tua
        LEFT JOIN `user` u          ON p.id_user = u.id_user
        LEFT JOIN jadwal_kegiatan j ON p.id_jadwal = j.id_jadwal
        ORDER BY p.id_pemeriksaan_balita ASC
        """
    )
    return render_template(
        "scorecard.html",
        rekap_periksa=rekap_periksa,
        active_sub="scorecard",
    )


@app.route("/halo/<nama>")
def halo(nama):
    """Contoh route dinamis sederhana yang menerima parameter pada URL."""
    return render_template("halo.html", nama=nama)


# ---------------------------------------------------------------------------
# TAHAP 2 : Menampilkan Data dari Database (READ: Daftar & Detail + 404)
# ---------------------------------------------------------------------------

# ---------- BALITA ----------
@app.route("/balita")
def daftar_balita():
    q = request.args.get("q", "").strip()
    jk = request.args.get("jk", "").strip()
    usia = request.args.get("usia", "").strip()

    sql = """
        SELECT b.id_balita, b.id_orang_tua, b.nama_balita, b.jenis_kelamin,
               b.tanggal_lahir, o.nama_ibu, o.alamat
        FROM balita b
        LEFT JOIN orang_tua o ON b.id_orang_tua = o.id_orang_tua
        WHERE 1 = 1
    """
    params = []
    if q:
        sql += " AND (b.nama_balita LIKE %s OR o.nama_ibu LIKE %s OR o.alamat LIKE %s)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if jk:
        sql += " AND b.jenis_kelamin = %s"
        params.append(jk)
    sql += " ORDER BY b.id_balita ASC"

    data = query_all(sql, params)
    if usia == "0-2":
        data = [b for b in data if (_umur_bulan(b.get("tanggal_lahir")) or 0) <= 24]
    elif usia == "2-6":
        data = [b for b in data if (_umur_bulan(b.get("tanggal_lahir")) or 0) > 24]

    active_sub = f"balita_{usia}" if usia else "balita"
    return render_template(
        "balita/daftar.html",
        data=data,
        q=q,
        jk=jk,
        usia=usia,
        active_sub=active_sub,
    )


@app.route("/balita/<int:id_balita>")
def detail_balita(id_balita):
    balita = query_one(
        """
        SELECT b.*, o.nama_ibu, o.alamat, o.no_hp
        FROM balita b
        LEFT JOIN orang_tua o ON b.id_orang_tua = o.id_orang_tua
        WHERE b.id_balita = %s
        """,
        (id_balita,),
    )
    if balita is None:
        abort(404)

    riwayat = query_all(
        """
        SELECT p.*, u.nama AS nama_petugas, j.lokasi
        FROM pemeriksaan_balita p
        LEFT JOIN `user` u          ON p.id_user = u.id_user
        LEFT JOIN jadwal_kegiatan j ON p.id_jadwal = j.id_jadwal
        WHERE p.id_balita = %s
        ORDER BY p.tanggal_periksa DESC
        """,
        (id_balita,),
    )
    return render_template("balita/detail.html", balita=balita, riwayat=riwayat, active_sub="balita")


# ---------- ORANG TUA (KIA) ----------
@app.route("/orang-tua")
def daftar_orang_tua():
    q = request.args.get("q", "").strip()

    sql = """
        SELECT o.*, COUNT(b.id_balita) AS jumlah_anak
        FROM orang_tua o
        LEFT JOIN balita b ON b.id_orang_tua = o.id_orang_tua
        WHERE 1 = 1
    """
    params = []
    if q:
        sql += " AND (o.nama_ibu LIKE %s OR o.alamat LIKE %s OR o.no_hp LIKE %s)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    sql += " GROUP BY o.id_orang_tua ORDER BY o.id_orang_tua ASC"

    data = query_all(sql, params)
    return render_template("orang_tua/daftar.html", data=data, q=q, active_sub="kia")


@app.route("/orang-tua/<int:id_orang_tua>")
def detail_orang_tua(id_orang_tua):
    orang_tua = query_one(
        "SELECT * FROM orang_tua WHERE id_orang_tua = %s", (id_orang_tua,)
    )
    if orang_tua is None:
        abort(404)

    anak = query_all(
        "SELECT * FROM balita WHERE id_orang_tua = %s ORDER BY tanggal_lahir",
        (id_orang_tua,),
    )
    return render_template("orang_tua/detail.html", orang_tua=orang_tua, anak=anak, active_sub="kia")


# ---------- PEMERIKSAAN ----------
@app.route("/pemeriksaan")
def daftar_pemeriksaan():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    sql = """
        SELECT p.id_pemeriksaan_balita, p.tanggal_periksa, p.berat_badan,
               p.tinggi_badan, p.lingkar_kepala, p.lingkar_lengan,
               p.status_gizi, p.catatan,
               b.id_balita, b.nama_balita, u.nama AS nama_petugas, j.lokasi
        FROM pemeriksaan_balita p
        LEFT JOIN balita b          ON p.id_balita = b.id_balita
        LEFT JOIN `user` u          ON p.id_user = u.id_user
        LEFT JOIN jadwal_kegiatan j ON p.id_jadwal = j.id_jadwal
        WHERE 1 = 1
    """
    params = []
    if q:
        sql += " AND (b.nama_balita LIKE %s OR u.nama LIKE %s OR p.status_gizi LIKE %s)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if status == "pantau":
        sql += " AND LOWER(p.status_gizi) NOT LIKE %s"
        params.append("%baik%")
    elif status:
        sql += " AND p.status_gizi = %s"
        params.append(status)
    sql += " ORDER BY p.id_pemeriksaan_balita ASC"

    data = query_all(sql, params)
    active_sub = f"periksa_{status}" if status else "pemeriksaan"
    return render_template(
        "pemeriksaan/daftar.html",
        data=data,
        q=q,
        status=status,
        active_sub=active_sub,
    )


@app.route("/pemeriksaan/<int:id_pemeriksaan>")
def detail_pemeriksaan(id_pemeriksaan):
    periksa = query_one(
        """
        SELECT p.*, b.nama_balita, b.jenis_kelamin, b.tanggal_lahir,
               u.nama AS nama_petugas, u.peran,
               j.tanggal_kegiatan, j.lokasi
        FROM pemeriksaan_balita p
        LEFT JOIN balita b          ON p.id_balita = b.id_balita
        LEFT JOIN `user` u          ON p.id_user = u.id_user
        LEFT JOIN jadwal_kegiatan j ON p.id_jadwal = j.id_jadwal
        WHERE p.id_pemeriksaan_balita = %s
        """,
        (id_pemeriksaan,),
    )
    if periksa is None:
        abort(404)
    return render_template("pemeriksaan/detail.html", periksa=periksa, active_sub="pemeriksaan")


# ---------- JADWAL KEGIATAN / POSYANDU ----------
@app.route("/jadwal")
def daftar_jadwal():
    q = request.args.get("q", "").strip()

    sql = """
        SELECT j.*, u.nama AS nama_petugas
        FROM jadwal_kegiatan j
        LEFT JOIN `user` u ON j.id_user = u.id_user
        WHERE 1 = 1
    """
    params = []
    if q:
        sql += " AND (j.lokasi LIKE %s OR j.keterangan_jadwal LIKE %s OR u.nama LIKE %s)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    sql += " ORDER BY j.id_jadwal ASC"

    data = query_all(sql, params)
    return render_template(
        "jadwal/daftar.html",
        data=data,
        q=q,
        hari_ini=date.today(),
        active_sub="jadwal",
    )


@app.route("/jadwal/<int:id_jadwal>")
def detail_jadwal(id_jadwal):
    jadwal = query_one(
        """
        SELECT j.*, u.nama AS nama_petugas, u.no_hp AS hp_petugas
        FROM jadwal_kegiatan j
        LEFT JOIN `user` u ON j.id_user = u.id_user
        WHERE j.id_jadwal = %s
        """,
        (id_jadwal,),
    )
    if jadwal is None:
        abort(404)

    pemeriksaan = query_all(
        """
        SELECT p.id_pemeriksaan_balita, p.tanggal_periksa, p.berat_badan,
               p.tinggi_badan, p.status_gizi, b.nama_balita
        FROM pemeriksaan_balita p
        LEFT JOIN balita b ON p.id_balita = b.id_balita
        WHERE p.id_jadwal = %s
        ORDER BY b.nama_balita
        """,
        (id_jadwal,),
    )
    return render_template(
        "jadwal/detail.html",
        jadwal=jadwal,
        pemeriksaan=pemeriksaan,
        active_sub="jadwal",
    )


# ---------- PETUGAS (tabel user) ----------
@app.route("/petugas")
def daftar_petugas():
    q = request.args.get("q", "").strip()

    sql = "SELECT id_user, nama, username, peran, no_hp FROM `user` WHERE 1 = 1"
    params = []
    if q:
        sql += " AND (nama LIKE %s OR peran LIKE %s OR username LIKE %s)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    sql += " ORDER BY id_user ASC"

    data = query_all(sql, params)
    return render_template("petugas/daftar.html", data=data, q=q, active_sub="petugas")


@app.route("/petugas/<int:id_user>")
def detail_petugas(id_user):
    petugas = query_one(
        "SELECT id_user, nama, username, peran, no_hp FROM `user` WHERE id_user = %s",
        (id_user,),
    )
    if petugas is None:
        abort(404)

    jadwal = query_all(
        "SELECT * FROM jadwal_kegiatan WHERE id_user = %s ORDER BY tanggal_kegiatan DESC",
        (id_user,),
    )
    jumlah_periksa = query_one(
        "SELECT COUNT(*) AS total FROM pemeriksaan_balita WHERE id_user = %s",
        (id_user,),
    )
    return render_template(
        "petugas/detail.html",
        petugas=petugas,
        jadwal=jadwal,
        jumlah_periksa=(jumlah_periksa or {}).get("total", 0),
        active_sub="petugas",
    )


# ---------------------------------------------------------------------------
# Penanganan error
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def halaman_tidak_ditemukan(_error):
    return render_template("404.html"), 404


@app.errorhandler(pymysql.MySQLError)
def database_error(error):
    return render_template("db_error.html", pesan=str(error)), 500


if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
