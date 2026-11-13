
import base64
import io
import math
import zipfile
from html import escape
from urllib.parse import quote

import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

# =========================================================
# MSN SMARTCARE - Prototype Business Plan Technopreneur
# CV Mitra Solution Network
# Fitur:
# 1. Dashboard ringkasan pelanggan
# 2. Data perangkat CCTV/PABX/Roller Blind
# 3. Status garansi dan maintenance
# 4. Form ticket kerusakan
# 5. Simulasi pendapatan dan BEP (margin proyek + subscription)
# 6. Simulasi ROE dan ROA
# 7. Pipeline proyek (Lead -> Survey -> Penawaran -> Instalasi)
# 8. QR Aset perangkat
# 9. Kontrak AMC & Subscription
# 10. Laporan digital per pelanggan
# 11. Rencana investasi & roadmap
# =========================================================

APP_TITLE = "MSN SmartCare"
DB_PATH = Path("msn_smartcare.db")

# Master pilihan - disesuaikan dengan isi PPT (slide 4, 13, 19, 20)
DEVICE_TYPES = ["CCTV", "PABX", "LAN/Fiber Optik", "Cable Tray", "Roller Blind", "iPad Charging Box"]
CUSTOMER_CATEGORIES = [
    "Sekolah & Kampus", "Perkantoran & Ruko", "Perumahan/Cluster",
    "Klinik/Rumah Sakit", "Korporasi & Properti", "Pemerintahan & Institusi", "Lainnya"
]
PIPELINE_STAGES = ["Lead/Request", "Survey Lokasi", "Penawaran", "Instalasi", "Selesai"]
CONTRACT_TYPES = ["Subscription SmartCare", "AMC 6 Bulan", "AMC 12 Bulan"]
CONTRACT_STATUSES = ["Aktif", "Berakhir", "Dibatalkan"]
# Normalisasi kategori lama agar sama dengan istilah di PPT
CATEGORY_MIGRATION = {
    "Kampus": "Sekolah & Kampus", "Kampus/Sekolah": "Sekolah & Kampus",
    "Perkantoran": "Perkantoran & Ruko", "Ruko": "Perkantoran & Ruko",
    "Perumahan": "Perumahan/Cluster",
}

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------
# Helper database
# -----------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            pic TEXT,
            phone TEXT,
            address TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            device_code TEXT UNIQUE NOT NULL,
            device_name TEXT NOT NULL,
            device_type TEXT NOT NULL,
            brand TEXT,
            location TEXT,
            install_date TEXT NOT NULL,
            warranty_months INTEGER DEFAULT 12,
            last_maintenance TEXT,
            maintenance_interval_days INTEGER DEFAULT 90,
            status TEXT DEFAULT 'Aktif',
            notes TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            device_id INTEGER,
            ticket_no TEXT UNIQUE NOT NULL,
            created_date TEXT NOT NULL,
            priority TEXT NOT NULL,
            problem TEXT NOT NULL,
            status TEXT DEFAULT 'Open',
            technician TEXT,
            resolution TEXT,
            closed_date TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(device_id) REFERENCES devices(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            maintenance_date TEXT NOT NULL,
            activity TEXT NOT NULL,
            technician TEXT,
            result TEXT,
            FOREIGN KEY(device_id) REFERENCES devices(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS revenue_simulations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            simulation_name TEXT,
            projects_per_month INTEGER,
            gross_profit_per_project REAL,
            subscriptions INTEGER,
            profit_per_subscription REAL,
            fixed_cost REAL,
            initial_investment REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_name TEXT NOT NULL,
            segment TEXT,
            service TEXT,
            stage TEXT DEFAULT 'Lead/Request',
            est_value REAL DEFAULT 0,
            contact TEXT,
            created_date TEXT NOT NULL,
            notes TEXT,
            customer_id INTEGER,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            contract_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            duration_months INTEGER DEFAULT 12,
            monthly_fee REAL DEFAULT 0,
            status TEXT DEFAULT 'Aktif',
            notes TEXT,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )
    """)

    conn.commit()
    seed_data(conn)
    migrate_and_seed_extra(conn)
    conn.close()

def migrate_and_seed_extra(conn):
    """Normalisasi kategori pelanggan + data contoh untuk pipeline & kontrak (hanya jika kosong)."""
    cur = conn.cursor()
    for old, new in CATEGORY_MIGRATION.items():
        cur.execute("UPDATE customers SET category=? WHERE category=?", (new, old))

    if cur.execute("SELECT COUNT(*) AS n FROM leads").fetchone()["n"] == 0:
        today = date.today()
        cur.executemany("""
            INSERT INTO leads(lead_name, segment, service, stage, est_value, contact, created_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            ("SMK Contoh Nusantara", "Sekolah & Kampus", "CCTV + LAN/Fiber Optik", "Survey Lokasi",
             18_000_000, "0812-0000-0001", str(today - timedelta(days=6)), "Data contoh"),
            ("Klinik Sehat Contoh", "Klinik/Rumah Sakit", "CCTV + Roller Blind", "Penawaran",
             25_000_000, "0812-0000-0002", str(today - timedelta(days=12)), "Data contoh"),
            ("Ruko Mega Contoh", "Perkantoran & Ruko", "PABX + Cable Tray", "Lead/Request",
             12_000_000, "0812-0000-0003", str(today - timedelta(days=1)), "Data contoh"),
        ])

    if cur.execute("SELECT COUNT(*) AS n FROM contracts").fetchone()["n"] == 0:
        cust = {r["name"]: r["id"] for r in cur.execute("SELECT id, name FROM customers").fetchall()}
        today = date.today()
        samples = [
            ("PT Graha Digital", "Subscription SmartCare", 60, 12, 400_000),
            ("Universitas Contoh", "AMC 12 Bulan", 100, 12, 400_000),
        ]
        for name, ctype, days_ago, months, fee in samples:
            if name in cust:
                cur.execute("""
                    INSERT INTO contracts(customer_id, contract_type, start_date, duration_months,
                                          monthly_fee, status, notes)
                    VALUES (?, ?, ?, ?, ?, 'Aktif', 'Data contoh')
                """, (cust[name], ctype, str(today - timedelta(days=days_ago)), months, fee))
    conn.commit()

def seed_data(conn):
    cur = conn.cursor()
    count = cur.execute("SELECT COUNT(*) AS n FROM customers").fetchone()["n"]
    if count > 0:
        return

    customers = [
        ("Universitas Contoh", "Sekolah & Kampus", "Budi Santoso", "0812-1111-2222", "Jakarta"),
        ("PT Graha Digital", "Perkantoran & Ruko", "Siti Rahma", "0813-3333-4444", "Tangerang"),
        ("Cluster Harmoni", "Perumahan/Cluster", "Andi Pratama", "0815-5555-6666", "Tangerang"),
    ]
    cur.executemany("""
        INSERT INTO customers(name, category, pic, phone, address)
        VALUES (?, ?, ?, ?, ?)
    """, customers)
    conn.commit()

    cust = cur.execute("SELECT id, name FROM customers").fetchall()
    cust_map = {r["name"]: r["id"] for r in cust}

    today = date.today()
    devices = [
        (
            cust_map["Universitas Contoh"], "CCTV-001", "CCTV Lobby", "CCTV",
            "Hikvision", "Gedung A - Lobby",
            str(today - timedelta(days=220)), 12,
            str(today - timedelta(days=65)), 90, "Aktif", "Kamera dome indoor"
        ),
        (
            cust_map["Universitas Contoh"], "PABX-001", "IP-PBX Rektorat", "PABX",
            "Yeastar", "Gedung Rektorat - Server Room",
            str(today - timedelta(days=400)), 12,
            str(today - timedelta(days=40)), 180, "Aktif", "40 extension"
        ),
        (
            cust_map["PT Graha Digital"], "RBL-001", "Roller Blind Meeting 1", "Roller Blind",
            "Somfy", "Meeting Room Lt. 5",
            str(today - timedelta(days=120)), 12,
            str(today - timedelta(days=95)), 90, "Aktif", "Motorized roller blind"
        ),
        (
            cust_map["PT Graha Digital"], "CCTV-002", "CCTV Area Parkir", "CCTV",
            "Dahua", "Basement B1",
            str(today - timedelta(days=500)), 24,
            str(today - timedelta(days=130)), 90, "Maintenance", "Perlu pembersihan lensa"
        ),
        (
            cust_map["Cluster Harmoni"], "CCTV-003", "CCTV Pos Security", "CCTV",
            "Uniview", "Pos Keamanan",
            str(today - timedelta(days=40)), 12,
            None, 90, "Aktif", "Outdoor camera"
        ),
    ]

    cur.executemany("""
        INSERT INTO devices(
            customer_id, device_code, device_name, device_type, brand, location,
            install_date, warranty_months, last_maintenance, maintenance_interval_days,
            status, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, devices)

    conn.commit()

    dev_rows = cur.execute("SELECT id, device_code FROM devices").fetchall()
    dev_map = {r["device_code"]: r["id"] for r in dev_rows}

    tickets = [
        (
            cust_map["PT Graha Digital"], dev_map["CCTV-002"], "TKT-0001",
            str(today - timedelta(days=2)), "High",
            "Gambar CCTV parkir buram dan terkadang putus-putus.",
            "In Progress", "Teknisi A", "", None
        ),
        (
            cust_map["Universitas Contoh"], dev_map["PABX-001"], "TKT-0002",
            str(today - timedelta(days=10)), "Medium",
            "Beberapa extension tidak dapat melakukan panggilan keluar.",
            "Closed", "Teknisi B",
            "Konfigurasi trunk diperbaiki dan extension diuji ulang.",
            str(today - timedelta(days=8))
        ),
    ]
    cur.executemany("""
        INSERT INTO tickets(
            customer_id, device_id, ticket_no, created_date, priority,
            problem, status, technician, resolution, closed_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, tickets)
    conn.commit()

# -----------------------------
# Data helpers
# -----------------------------
def query_df(sql, params=()):
    conn = get_conn()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df

def next_ticket_no():
    conn = get_conn()
    row = conn.execute("SELECT MAX(id) AS max_id FROM tickets").fetchone()
    conn.close()
    next_id = (row["max_id"] or 0) + 1
    return f"TKT-{next_id:04d}"

def warranty_end(install_date, months):
    d = pd.to_datetime(install_date).date()
    months = 0 if pd.isna(months) else int(months)
    # Approximation by months using pandas offset
    return (pd.Timestamp(d) + pd.DateOffset(months=months)).date()

def maintenance_due(last_maintenance, install_date, interval_days):
    # Use pd.isna() instead of a plain truthy check: NaN/NaT values coming
    # back from pandas (e.g. when last_maintenance is NULL for every row)
    # are truthy in Python, so a bare `if last_maintenance` would wrongly
    # keep them instead of falling back to install_date.
    has_last_maintenance = last_maintenance is not None and not pd.isna(last_maintenance) and str(last_maintenance).strip() != ""
    base_value = last_maintenance if has_last_maintenance else install_date
    base = pd.to_datetime(base_value).date()
    interval_days = 90 if pd.isna(interval_days) else int(interval_days)
    return base + timedelta(days=interval_days)

def get_warranty_status(install_date, months):
    try:
        end = warranty_end(install_date, months)
        if pd.isna(end):
            return "Tidak Diketahui"
        delta = (end - date.today()).days
    except (TypeError, ValueError):
        return "Tidak Diketahui"
    if delta < 0:
        return "Expired"
    elif delta <= 30:
        return "Segera Berakhir"
    return "Aktif"

def get_maintenance_status(last_maintenance, install_date, interval_days):
    try:
        due = maintenance_due(last_maintenance, install_date, interval_days)
        if pd.isna(due):
            return "Tidak Diketahui"
        delta = (due - date.today()).days
    except (TypeError, ValueError):
        return "Tidak Diketahui"
    if delta < 0:
        return "Terlambat"
    elif delta <= 14:
        return "Jatuh Tempo"
    return "Terjadwal"

def rupiah(x):
    try:
        return "Rp {:,.0f}".format(float(x)).replace(",", ".")
    except:
        return str(x)

def enrich_devices(df):
    """Tambah kolom garansi & maintenance turunan pada dataframe perangkat."""
    df = df.copy()
    if df.empty:
        return df
    df["warranty_end"] = df.apply(lambda r: warranty_end(r["install_date"], r["warranty_months"]), axis=1)
    df["warranty_status"] = df.apply(lambda r: get_warranty_status(r["install_date"], r["warranty_months"]), axis=1)
    df["next_maintenance"] = df.apply(
        lambda r: maintenance_due(r["last_maintenance"], r["install_date"], r["maintenance_interval_days"]), axis=1)
    df["maintenance_status"] = df.apply(
        lambda r: get_maintenance_status(r["last_maintenance"], r["install_date"], r["maintenance_interval_days"]), axis=1)
    return df

def show_df_or_info(df, empty_msg):
    """Tampilkan tabel, atau pesan info jika kosong (pakai if/else biasa agar tidak memicu 'magic' Streamlit)."""
    if df is None or df.empty:
        st.info(empty_msg)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

LOGO_SVG = (
    '<svg viewBox="0 0 70 40" xmlns="http://www.w3.org/2000/svg" width="100%" height="100%">'
    '<path d="M10 6 L22 2 L34 6 V18 C34 26 29 31 22 34 C15 31 10 26 10 18 Z" fill="#1b2a4e"/>'
    '<path d="M16 18 l4 4 l8 -9" stroke="#ffffff" stroke-width="3" fill="none" '
    'stroke-linecap="round" stroke-linejoin="round"/>'
    '<text x="38" y="17" font-family="Arial,sans-serif" font-weight="800" font-size="10" fill="#1b2a4e">MSN</text>'
    '<text x="38" y="27" font-family="Arial,sans-serif" font-weight="700" font-size="6" fill="#b71c1c">CARE</text>'
    '</svg>'
)

def logo_html():
    """Pakai logo.png / logo.jpg / logo.svg di folder aplikasi jika ada; jika tidak, pakai logo bawaan."""
    for fname, mime in (("logo.png", "image/png"), ("logo.jpg", "image/jpeg"),
                        ("logo.jpeg", "image/jpeg"), ("logo.svg", "image/svg+xml")):
        p = Path(fname)
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode()
            return f'<img src="data:{mime};base64,{b64}" alt="logo" style="max-width:100%;max-height:100%;">'
    return LOGO_SVG

BRAND_HTML = (
    '<div class="brand">'
    '<div class="brand-logo">__LOGO__</div>'
    '<div><div class="brand-title">MSN SmartCare</div>'
    '<div class="brand-sub">CV Mitra Solution Network</div></div>'
    '</div>'
)

def qr_png_bytes(text):
    """Buat QR code PNG. Mengembalikan None jika paket 'qrcode' belum terpasang."""
    try:
        import qrcode
    except ImportError:
        return None
    img = qrcode.make(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def qr_payload(code, name, customer, location, base_url=""):
    base_url = (base_url or "").strip()
    if base_url:
        return f"{base_url.rstrip('/')}/?device={quote(code)}"
    return f"MSN SmartCare\nKode: {code}\nPerangkat: {name}\nPelanggan: {customer}\nLokasi: {location or '-'}"

def render_device_detail(code):
    """Halaman detail perangkat yang dibuka dari scan QR (?device=KODE)."""
    df = query_df("""
        SELECT d.*, c.name AS customer_name, c.pic, c.phone
        FROM devices d JOIN customers c ON c.id = d.customer_id
        WHERE d.device_code = ?
    """, (code,))
    st.markdown('<div class="main-title">Detail Perangkat</div>', unsafe_allow_html=True)
    if df.empty:
        st.error(f"Perangkat dengan kode {code} tidak ditemukan.")
        return
    df = enrich_devices(df)
    r = df.iloc[0]
    st.markdown(f'<div class="sub-title">{escape(str(r["device_code"]))} - {escape(str(r["device_name"]))}</div>',
                unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    m1.metric("Status Perangkat", r["status"])
    m2.metric("Garansi", r["warranty_status"], help=f"Berakhir {r['warranty_end']}")
    m3.metric("Maintenance", r["maintenance_status"], help=f"Jadwal berikut {r['next_maintenance']}")
    st.write(f"**Pelanggan:** {r['customer_name']}  |  **PIC:** {r['pic'] or '-'}  |  **Telepon:** {r['phone'] or '-'}")
    st.write(f"**Jenis:** {r['device_type']}  |  **Merek:** {r['brand'] or '-'}  |  **Lokasi:** {r['location'] or '-'}")
    st.write(f"**Tanggal instalasi:** {r['install_date']}  |  **Garansi s/d:** {r['warranty_end']}  |  "
             f"**Maintenance terakhir:** {r['last_maintenance'] or '-'}")
    st.subheader("Riwayat Maintenance")
    logs = query_df("""SELECT maintenance_date, activity, technician, result
                       FROM maintenance_logs WHERE device_id=? ORDER BY id DESC""", (int(r["id"]),))
    if logs.empty:
        st.info("Belum ada riwayat maintenance.")
    else:
        st.dataframe(logs, use_container_width=True, hide_index=True)
    st.subheader("Riwayat Ticket")
    tk = query_df("""SELECT ticket_no, created_date, priority, problem, status, closed_date
                     FROM tickets WHERE device_id=? ORDER BY id DESC""", (int(r["id"]),))
    if tk.empty:
        st.info("Belum ada ticket untuk perangkat ini.")
    else:
        st.dataframe(tk, use_container_width=True, hide_index=True)

def build_report_html(customer, dev_view, tk_view, log_view, ct_view, summary):
    css = ("body{font-family:Arial,sans-serif;margin:32px;color:#123c5e}"
           "h1{margin-bottom:0}h2{margin-top:28px;border-bottom:2px solid #cfe0f3;padding-bottom:4px}"
           "table{border-collapse:collapse;width:100%;font-size:12px}"
           "th,td{border:1px solid #cfe0f3;padding:6px 8px;text-align:left;vertical-align:top}"
           "th{background:#eaf2fb}.sum span{display:inline-block;margin-right:24px}")
    def tbl(df):
        return "<p><i>Tidak ada data.</i></p>" if df.empty else df.to_html(index=False, border=0)
    s = "".join(f"<span><b>{escape(k)}:</b> {escape(str(v))}</span>" for k, v in summary.items())
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>Laporan {escape(str(customer['name']))}</title><style>{css}</style></head><body>"
        "<h1>Laporan Layanan MSN SmartCare</h1>"
        f"<p>CV Mitra Solution Network | Dicetak: {date.today()}</p>"
        f"<h2>Pelanggan</h2><p><b>{escape(str(customer['name']))}</b> ({escape(str(customer['category'] or '-'))})<br>"
        f"PIC: {escape(str(customer['pic'] or '-'))} | Telepon: {escape(str(customer['phone'] or '-'))}<br>"
        f"Alamat: {escape(str(customer['address'] or '-'))}</p>"
        f"<div class='sum'>{s}</div>"
        f"<h2>Perangkat, Garansi & Maintenance</h2>{tbl(dev_view)}"
        f"<h2>Riwayat Maintenance</h2>{tbl(log_view)}"
        f"<h2>Ticket Kerusakan</h2>{tbl(tk_view)}"
        f"<h2>Kontrak AMC & Subscription</h2>{tbl(ct_view)}"
        "</body></html>"
    )

def pct_id(x, decimals=0):
    """Format persen gaya Indonesia, mis. 96% atau 12,5%."""
    s = f"{x:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + "%"

def num_id(x, decimals=2):
    """Format angka desimal gaya Indonesia, mis. 0,96."""
    return f"{x:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")

# -----------------------------
# Styling
# -----------------------------
st.markdown("""
<style>
    .main-title {
        font-size: 2.0rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #666;
        margin-bottom: 1.2rem;
    }
    .small-note {
        font-size: 0.85rem;
        color: #777;
    }
    .ratio-card {
        border-radius: 32px;
        padding: 1.6rem 1.5rem;
        min-height: 480px;
        display: flex;
        flex-direction: column;
    }
    .ratio-light {
        background: #f8fbff;
        border: 2px solid #cfe0f3;
        color: #123c5e;
    }
    .ratio-dark {
        background: #123c5e;
        border: 2px solid #123c5e;
        color: #ffffff;
    }
    .ratio-label {
        font-size: 0.8rem;
        font-weight: 800;
        letter-spacing: 0.02em;
        color: #1e88e5;
        text-transform: uppercase;
    }
    .ratio-name { font-size: 2.2rem; font-weight: 800; margin: 0.8rem 0 0.6rem 0; }
    .ratio-section { font-size: 0.95rem; margin-bottom: 1rem; line-height: 1.5; }
    .ratio-value { font-size: 3.4rem; font-weight: 800; text-align: center; margin-top: auto; line-height: 1.1; }
    .ratio-desc { font-size: 0.82rem; text-align: center; line-height: 1.45; margin-top: 0.4rem; }
    /* ===== Header & menu atas ===== */
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] { display: none !important; }
    header[data-testid="stHeader"] { display: none; }
    .block-container { padding-top: 0 !important; padding-left: 2rem !important;
                       padding-right: 2rem !important; max-width: 100% !important; }
    .topbar { background: #1b2a4e; border-bottom: 4px solid #b71c1c;
              margin: 0 -2rem 1.5rem -2rem; padding: 0.9rem 2rem 0.8rem 2rem; }
    .brand { display: flex; align-items: center; gap: 0.9rem; margin-bottom: 0.8rem; }
    .brand-logo { width: 64px; height: 44px; background: #ffffff; border-radius: 10px;
                  padding: 4px 6px; display: flex; align-items: center; justify-content: center; }
    .brand-title { color: #ffffff; font-size: 1.1rem; font-weight: 800; line-height: 1.2; }
    .brand-sub { color: #c9d3ea; font-size: 0.8rem; }
    .navbtns { display: flex; flex-wrap: wrap; gap: 0.3rem 0.35rem; }
    .navbtns a, .navbtns a:link, .navbtns a:visited {
        display: inline-block; padding: 0.5rem 0.95rem; border-radius: 8px;
        background: transparent; color: #ffffff !important; font-size: 0.93rem; font-weight: 500;
        text-decoration: none !important; line-height: 1.2; border: 0; }
    .navbtns a:hover { background: rgba(255,255,255,0.14); color: #ffffff !important; }
    .navbtns a.active, .navbtns a.active:visited {
        background: rgba(255,255,255,0.24); color: #ffffff !important; font-weight: 700; }
    .flow-wrap { display: flex; flex-wrap: wrap; gap: 0.6rem; margin: 0.5rem 0 1.2rem 0; }
    .flow-step { flex: 1 1 120px; border-radius: 16px; padding: 0.7rem 0.8rem; min-width: 120px; }
    .flow-pre { background: #9dc3e6; color: #123c5e; }
    .flow-post { background: #123c5e; color: #ffffff; }
    .flow-num { font-size: 0.75rem; font-weight: 800; opacity: 0.8; }
    .flow-name { font-size: 1rem; font-weight: 800; }
    .flow-sub { font-size: 0.72rem; opacity: 0.85; }
    .interpretation-box {
        background: #f5f9ff;
        border: 1.5px solid #cfe0f3;
        border-radius: 12px;
        padding: 0.7rem 1rem;
        text-align: center;
        font-weight: 700;
        color: #123c5e;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# App start
# -----------------------------
init_db()

MENU_ITEMS = [
    ("dashboard", "Dashboard"),
    ("pipeline", "Pipeline Proyek"),
    ("perangkat", "Data Perangkat"),
    ("qr", "QR Aset"),
    ("garansi", "Garansi & Maintenance"),
    ("ticket", "Ticket Kerusakan"),
    ("kontrak", "Kontrak & Subscription"),
    ("laporan", "Laporan Digital"),
    ("bep", "Simulasi Pendapatan & BEP"),
    ("roe-roa", "Simulasi ROE & ROA"),
    ("investasi", "Rencana Investasi"),
    ("pelanggan", "Data Pelanggan"),
]

def nav_html(active_slug):
    links = "".join(
        f'<a href="?menu={slug}" target="_self" class="{"active" if slug == active_slug else ""}">{escape(label)}</a>'
        for slug, label in MENU_ITEMS
    )
    return f'<div class="navbtns">{links}</div>'

brand_html = BRAND_HTML.replace("__LOGO__", logo_html())

# Halaman detail perangkat jika QR di-scan (?device=KODE)
scan_code = st.query_params.get("device")
if scan_code:
    st.markdown(f'<div class="topbar">{brand_html}</div>', unsafe_allow_html=True)
    render_device_detail(scan_code)
    if st.button("Buka aplikasi MSN SmartCare"):
        st.query_params.clear()
        st.rerun()
    st.stop()

# Menu aktif dibaca dari ?menu=... (default: Dashboard)
slug_to_label = dict(MENU_ITEMS)
active_slug = st.query_params.get("menu", MENU_ITEMS[0][0])
if active_slug not in slug_to_label:
    active_slug = MENU_ITEMS[0][0]
menu = slug_to_label[active_slug]

st.markdown(f'<div class="topbar">{brand_html}{nav_html(active_slug)}</div>', unsafe_allow_html=True)

# =========================================================
# 1. DASHBOARD
# =========================================================
if menu == "Dashboard":
    st.markdown('<div class="main-title">Dashboard Ringkasan Pelanggan</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Monitoring pelanggan, perangkat, tiket, garansi, dan maintenance.</div>', unsafe_allow_html=True)

    customers = query_df("SELECT * FROM customers ORDER BY name")
    devices = query_df("""
        SELECT d.*, c.name AS customer_name
        FROM devices d
        JOIN customers c ON c.id = d.customer_id
        ORDER BY d.id DESC
    """)
    tickets = query_df("""
        SELECT t.*, c.name AS customer_name, d.device_code, d.device_name
        FROM tickets t
        JOIN customers c ON c.id = t.customer_id
        LEFT JOIN devices d ON d.id = t.device_id
        ORDER BY t.id DESC
    """)

    # derive status
    if not devices.empty:
        devices["warranty_status"] = devices.apply(
            lambda r: get_warranty_status(r["install_date"], r["warranty_months"]), axis=1
        )
        devices["maintenance_status"] = devices.apply(
            lambda r: get_maintenance_status(
                r["last_maintenance"], r["install_date"], r["maintenance_interval_days"]
            ), axis=1
        )

    open_tickets = 0 if tickets.empty else int((tickets["status"] != "Closed").sum())
    due_maintenance = 0 if devices.empty else int(devices["maintenance_status"].isin(["Terlambat", "Jatuh Tempo"]).sum())
    warranty_attention = 0 if devices.empty else int(devices["warranty_status"].isin(["Expired", "Segera Berakhir"]).sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Pelanggan", len(customers))
    c2.metric("Perangkat", len(devices))
    c3.metric("Ticket Aktif", open_tickets)
    c4.metric("Maintenance Perlu Perhatian", due_maintenance)
    c5.metric("Garansi Perlu Perhatian", warranty_attention)

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Komposisi Perangkat")
        if devices.empty:
            st.info("Belum ada data perangkat.")
        else:
            chart = devices.groupby("device_type").size().reset_index(name="jumlah")
            st.bar_chart(chart.set_index("device_type"))

    with col_b:
        st.subheader("Status Ticket")
        if tickets.empty:
            st.info("Belum ada ticket.")
        else:
            chart = tickets.groupby("status").size().reset_index(name="jumlah")
            st.bar_chart(chart.set_index("status"))

    st.subheader("Ticket Terbaru")
    if tickets.empty:
        st.info("Belum ada ticket.")
    else:
        show_cols = [
            "ticket_no", "customer_name", "device_code",
            "priority", "problem", "status", "created_date"
        ]
        st.dataframe(tickets[show_cols].head(10), use_container_width=True, hide_index=True)

    st.subheader("Maintenance yang Perlu Segera Ditangani")
    if devices.empty:
        st.info("Belum ada data perangkat.")
    else:
        attention = devices[devices["maintenance_status"].isin(["Terlambat", "Jatuh Tempo"])].copy()
        if attention.empty:
            st.success("Tidak ada maintenance yang jatuh tempo.")
        else:
            attention["next_maintenance"] = attention.apply(
                lambda r: maintenance_due(
                    r["last_maintenance"], r["install_date"], r["maintenance_interval_days"]
                ), axis=1
            )
            st.dataframe(
                attention[
                    ["device_code", "device_name", "customer_name",
                     "device_type", "next_maintenance", "maintenance_status"]
                ],
                use_container_width=True,
                hide_index=True
            )

# =========================================================
# 2. DATA PERANGKAT
# =========================================================
elif menu == "Data Perangkat":
    st.markdown('<div class="main-title">Data Perangkat</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Inventaris CCTV, PABX, LAN/Fiber Optik, Cable Tray, Roller Blind, dan iPad Charging Box.</div>', unsafe_allow_html=True)

    customers = query_df("SELECT id, name FROM customers ORDER BY name")
    customer_map = dict(zip(customers["name"], customers["id"])) if not customers.empty else {}

    with st.expander("➕ Tambah Perangkat Baru", expanded=False):
        with st.form("form_add_device"):
            col1, col2 = st.columns(2)

            with col1:
                customer_name = st.selectbox("Pelanggan", list(customer_map.keys()))
                device_code = st.text_input("Kode Perangkat", placeholder="Contoh: CCTV-010")
                device_name = st.text_input("Nama Perangkat", placeholder="Contoh: CCTV Lobby Utama")
                device_type = st.selectbox("Jenis Perangkat", DEVICE_TYPES)
                brand = st.text_input("Merek")

            with col2:
                location = st.text_input("Lokasi Pemasangan")
                install_date = st.date_input("Tanggal Instalasi", value=date.today())
                warranty_months = st.number_input("Garansi (bulan)", 0, 60, 12)
                interval_days = st.number_input("Interval Maintenance (hari)", 7, 365, 90)
                status = st.selectbox("Status Perangkat", ["Aktif", "Maintenance", "Rusak", "Nonaktif"])

            notes = st.text_area("Catatan")
            submit = st.form_submit_button("Simpan Perangkat", type="primary")

            if submit:
                if not device_code.strip() or not device_name.strip():
                    st.error("Kode perangkat dan nama perangkat wajib diisi.")
                elif not customer_map:
                    st.error("Belum ada pelanggan.")
                else:
                    try:
                        conn = get_conn()
                        conn.execute("""
                            INSERT INTO devices(
                                customer_id, device_code, device_name, device_type,
                                brand, location, install_date, warranty_months,
                                last_maintenance, maintenance_interval_days, status, notes
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            customer_map[customer_name], device_code.strip(),
                            device_name.strip(), device_type, brand.strip(),
                            location.strip(), str(install_date), int(warranty_months),
                            None, int(interval_days), status, notes.strip()
                        ))
                        conn.commit()
                        conn.close()
                        st.success("Perangkat berhasil ditambahkan.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Kode perangkat sudah digunakan.")

    st.subheader("Daftar Perangkat")

    df = query_df("""
        SELECT
            d.id, d.device_code, d.device_name, d.device_type, d.brand,
            d.location, d.install_date, d.warranty_months,
            d.last_maintenance, d.maintenance_interval_days,
            d.status, d.notes, c.name AS customer_name
        FROM devices d
        JOIN customers c ON c.id = d.customer_id
        ORDER BY d.id DESC
    """)

    if df.empty:
        st.info("Belum ada perangkat.")
    else:
        f1, f2 = st.columns(2)
        customer_filter = f1.selectbox(
            "Filter pelanggan",
            ["Semua"] + sorted(df["customer_name"].unique().tolist())
        )
        type_filter = f2.selectbox(
            "Filter jenis",
            ["Semua"] + sorted(df["device_type"].unique().tolist())
        )

        filtered = df.copy()
        if customer_filter != "Semua":
            filtered = filtered[filtered["customer_name"] == customer_filter]
        if type_filter != "Semua":
            filtered = filtered[filtered["device_type"] == type_filter]

        st.dataframe(
            filtered[
                [
                    "device_code", "device_name", "device_type", "brand",
                    "customer_name", "location", "install_date",
                    "warranty_months", "last_maintenance", "status"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

# =========================================================
# 3. STATUS GARANSI & MAINTENANCE
# =========================================================
elif menu == "Garansi & Maintenance":
    st.markdown('<div class="main-title">Status Garansi dan Maintenance</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Pemantauan masa garansi dan jadwal preventive maintenance.</div>', unsafe_allow_html=True)

    df = query_df("""
        SELECT d.*, c.name AS customer_name
        FROM devices d
        JOIN customers c ON c.id = d.customer_id
        ORDER BY d.id DESC
    """)

    if df.empty:
        st.info("Belum ada perangkat.")
    else:
        df["warranty_end"] = df.apply(
            lambda r: warranty_end(r["install_date"], r["warranty_months"]), axis=1
        )
        df["warranty_status"] = df.apply(
            lambda r: get_warranty_status(r["install_date"], r["warranty_months"]), axis=1
        )
        df["next_maintenance"] = df.apply(
            lambda r: maintenance_due(
                r["last_maintenance"], r["install_date"], r["maintenance_interval_days"]
            ), axis=1
        )
        df["maintenance_status"] = df.apply(
            lambda r: get_maintenance_status(
                r["last_maintenance"], r["install_date"], r["maintenance_interval_days"]
            ), axis=1
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Garansi Aktif", int((df["warranty_status"] == "Aktif").sum()))
        c2.metric("Garansi Segera Berakhir", int((df["warranty_status"] == "Segera Berakhir").sum()))
        c3.metric("Maintenance Jatuh Tempo", int((df["maintenance_status"] == "Jatuh Tempo").sum()))
        c4.metric("Maintenance Terlambat", int((df["maintenance_status"] == "Terlambat").sum()))

        st.subheader("Monitoring Garansi")
        st.dataframe(
            df[
                [
                    "device_code", "device_name", "customer_name",
                    "install_date", "warranty_months",
                    "warranty_end", "warranty_status"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

        st.subheader("Monitoring Maintenance")
        st.dataframe(
            df[
                [
                    "device_code", "device_name", "customer_name",
                    "last_maintenance", "maintenance_interval_days",
                    "next_maintenance", "maintenance_status"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

        with st.expander("🧰 Catat Maintenance Baru"):
            device_options = {
                f'{r["device_code"]} - {r["device_name"]} - {r["customer_name"]}': int(r["id"])
                for _, r in df.iterrows()
            }

            with st.form("maintenance_form"):
                selected = st.selectbox("Pilih Perangkat", list(device_options.keys()))
                maintenance_date = st.date_input("Tanggal Maintenance", value=date.today())
                activity = st.text_area(
                    "Aktivitas",
                    value="Pemeriksaan kondisi, pembersihan, pengujian fungsi, dan pengecekan koneksi."
                )
                technician = st.text_input("Teknisi")
                result = st.text_area("Hasil / Catatan")
                save_maintenance = st.form_submit_button("Simpan Maintenance", type="primary")

                if save_maintenance:
                    device_id = device_options[selected]
                    conn = get_conn()
                    conn.execute("""
                        INSERT INTO maintenance_logs(
                            device_id, maintenance_date, activity, technician, result
                        )
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        device_id, str(maintenance_date),
                        activity.strip(), technician.strip(), result.strip()
                    ))
                    conn.execute("""
                        UPDATE devices
                        SET last_maintenance=?, status='Aktif'
                        WHERE id=?
                    """, (str(maintenance_date), device_id))
                    conn.commit()
                    conn.close()
                    st.success("Riwayat maintenance berhasil disimpan.")
                    st.rerun()

        st.subheader("Riwayat Maintenance")
        logs = query_df("""
            SELECT
                m.maintenance_date, d.device_code, d.device_name,
                c.name AS customer_name, m.activity,
                m.technician, m.result
            FROM maintenance_logs m
            JOIN devices d ON d.id = m.device_id
            JOIN customers c ON c.id = d.customer_id
            ORDER BY m.id DESC
        """)
        if logs.empty:
            st.info("Belum ada riwayat maintenance.")
        else:
            st.dataframe(logs, use_container_width=True, hide_index=True)

# =========================================================
# 4. FORM TICKET KERUSAKAN
# =========================================================
elif menu == "Ticket Kerusakan":
    st.markdown('<div class="main-title">Ticket Kerusakan</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Pelanggan dapat melaporkan gangguan dan admin dapat memantau tindak lanjut.</div>', unsafe_allow_html=True)

    customers = query_df("SELECT id, name FROM customers ORDER BY name")
    customer_map = dict(zip(customers["name"], customers["id"])) if not customers.empty else {}

    st.subheader("Buat Ticket Baru")

    if not customer_map:
        st.warning("Tambahkan pelanggan terlebih dahulu.")
    else:
        customer_name = st.selectbox("Pelanggan", list(customer_map.keys()))
        customer_id = customer_map[customer_name]

        devices = query_df("""
            SELECT id, device_code, device_name
            FROM devices
            WHERE customer_id=?
            ORDER BY device_name
        """, (customer_id,))

        device_map = {
            f'{r["device_code"]} - {r["device_name"]}': int(r["id"])
            for _, r in devices.iterrows()
        }

        with st.form("ticket_form"):
            ticket_no = st.text_input("Nomor Ticket", value=next_ticket_no(), disabled=True)
            device_label = st.selectbox(
                "Perangkat",
                ["Tidak spesifik / Umum"] + list(device_map.keys())
            )
            priority = st.selectbox("Prioritas", ["Low", "Medium", "High", "Critical"])
            problem = st.text_area(
                "Deskripsi Kerusakan",
                placeholder="Contoh: Kamera CCTV lobby tidak tampil di monitor..."
            )
            submit_ticket = st.form_submit_button("Kirim Ticket", type="primary")

            if submit_ticket:
                if not problem.strip():
                    st.error("Deskripsi kerusakan wajib diisi.")
                else:
                    device_id = None if device_label == "Tidak spesifik / Umum" else device_map[device_label]
                    conn = get_conn()
                    conn.execute("""
                        INSERT INTO tickets(
                            customer_id, device_id, ticket_no, created_date,
                            priority, problem, status
                        )
                        VALUES (?, ?, ?, ?, ?, ?, 'Open')
                    """, (
                        customer_id, device_id, next_ticket_no(),
                        str(date.today()), priority, problem.strip()
                    ))
                    conn.commit()
                    conn.close()
                    st.success("Ticket berhasil dibuat.")
                    st.rerun()

    st.divider()
    st.subheader("Daftar Ticket")

    tickets = query_df("""
        SELECT
            t.id, t.ticket_no, t.created_date, t.priority, t.problem,
            t.status, t.technician, t.resolution, t.closed_date,
            c.name AS customer_name,
            d.device_code, d.device_name
        FROM tickets t
        JOIN customers c ON c.id = t.customer_id
        LEFT JOIN devices d ON d.id = t.device_id
        ORDER BY t.id DESC
    """)

    if tickets.empty:
        st.info("Belum ada ticket.")
    else:
        st.dataframe(
            tickets[
                [
                    "ticket_no", "created_date", "customer_name",
                    "device_code", "priority", "problem",
                    "status", "technician", "closed_date"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

        st.subheader("Update Ticket")
        ticket_map = {
            f'{r["ticket_no"]} - {r["customer_name"]} - {r["status"]}': int(r["id"])
            for _, r in tickets.iterrows()
        }

        with st.form("update_ticket_form"):
            selected_ticket = st.selectbox("Pilih Ticket", list(ticket_map.keys()))
            new_status = st.selectbox(
                "Status Baru",
                ["Open", "In Progress", "Waiting Part", "Resolved", "Closed"]
            )
            technician = st.text_input("Teknisi")
            resolution = st.text_area("Tindakan / Solusi")
            update = st.form_submit_button("Update Ticket", type="primary")

            if update:
                ticket_id = ticket_map[selected_ticket]
                closed_date = str(date.today()) if new_status == "Closed" else None
                conn = get_conn()
                conn.execute("""
                    UPDATE tickets
                    SET status=?, technician=?, resolution=?, closed_date=?
                    WHERE id=?
                """, (
                    new_status, technician.strip(),
                    resolution.strip(), closed_date, ticket_id
                ))
                conn.commit()
                conn.close()
                st.success("Ticket berhasil diperbarui.")
                st.rerun()

# =========================================================
# 7. PIPELINE PROYEK (Slide 13: Lead -> Survey -> Penawaran -> Instalasi)
# =========================================================
elif menu == "Pipeline Proyek":
    st.markdown('<div class="main-title">Pipeline Proyek</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Alur operasional digital: dari permintaan pelanggan sampai laporan maintenance.</div>',
        unsafe_allow_html=True
    )

    flow = [
        ("1", "Lead/Request", "Pipeline Proyek", "pre"),
        ("2", "Survey Lokasi", "Pipeline Proyek", "pre"),
        ("3", "Penawaran", "Pipeline Proyek", "pre"),
        ("4", "Instalasi", "Pipeline Proyek", "pre"),
        ("5", "QR Aset", "Menu QR Aset", "post"),
        ("6", "Ticketing", "Menu Ticket Kerusakan", "post"),
        ("7", "Maintenance", "Menu Garansi & Maintenance", "post"),
        ("8", "Laporan", "Menu Laporan Digital", "post"),
    ]
    flow_html = '<div class="flow-wrap">' + "".join(
        f'<div class="flow-step flow-{kind}"><div class="flow-num">{n} - '
        f'{"Tahap proyek awal" if kind == "pre" else "Layanan pasca proyek"}</div>'
        f'<div class="flow-name">{name}</div><div class="flow-sub">{menu_name}</div></div>'
        for n, name, menu_name, kind in flow
    ) + "</div>"
    st.markdown(flow_html, unsafe_allow_html=True)

    leads = query_df("SELECT * FROM leads ORDER BY id DESC")

    cols = st.columns(len(PIPELINE_STAGES))
    for col, stage in zip(cols, PIPELINE_STAGES):
        col.metric(stage, 0 if leads.empty else int((leads["stage"] == stage).sum()))
    running_value = 0 if leads.empty else float(leads.loc[leads["stage"] != "Selesai", "est_value"].sum())
    st.metric("Estimasi Nilai Proyek Berjalan (belum selesai)", rupiah(running_value))

    with st.expander("➕ Tambah Lead / Permintaan Baru", expanded=False):
        with st.form("lead_form"):
            a, b = st.columns(2)
            with a:
                lead_name = st.text_input("Nama Calon Pelanggan")
                segment = st.selectbox("Segmen", CUSTOMER_CATEGORIES)
                service = st.text_input("Layanan yang Diminta", placeholder="Contoh: CCTV + LAN/Fiber Optik")
            with b:
                est_value = st.number_input("Estimasi Nilai Proyek (Rp)", min_value=0, value=0, step=500_000)
                contact = st.text_input("Kontak / WhatsApp")
                notes = st.text_area("Catatan")
            add_lead = st.form_submit_button("Simpan Lead", type="primary")
            if add_lead:
                if not lead_name.strip():
                    st.error("Nama calon pelanggan wajib diisi.")
                else:
                    conn = get_conn()
                    conn.execute("""
                        INSERT INTO leads(lead_name, segment, service, stage, est_value, contact, created_date, notes)
                        VALUES (?, ?, ?, 'Lead/Request', ?, ?, ?, ?)
                    """, (lead_name.strip(), segment, service.strip(), float(est_value),
                          contact.strip(), str(date.today()), notes.strip()))
                    conn.commit()
                    conn.close()
                    st.success("Lead berhasil ditambahkan.")
                    st.rerun()

    st.subheader("Daftar Lead & Proyek")
    if leads.empty:
        st.info("Belum ada lead.")
    else:
        stage_filter = st.selectbox("Filter tahap", ["Semua"] + PIPELINE_STAGES)
        view = leads if stage_filter == "Semua" else leads[leads["stage"] == stage_filter]
        view = view.copy()
        view["est_value"] = view["est_value"].apply(rupiah)
        st.dataframe(
            view[["lead_name", "segment", "service", "stage", "est_value", "contact", "created_date", "notes"]],
            use_container_width=True, hide_index=True
        )

        st.subheader("Update Tahap Proyek")
        lead_map = {f'{r["lead_name"]} - {r["stage"]}': int(r["id"]) for _, r in leads.iterrows()}
        with st.form("lead_update_form"):
            selected = st.selectbox("Pilih Lead", list(lead_map.keys()))
            new_stage = st.selectbox("Tahap Baru", PIPELINE_STAGES)
            make_customer = st.checkbox(
                "Jika tahap 'Selesai', daftarkan otomatis sebagai pelanggan (bila belum terdaftar)", value=True
            )
            upd = st.form_submit_button("Update Tahap", type="primary")
            if upd:
                lead_id = lead_map[selected]
                lead = leads[leads["id"] == lead_id].iloc[0]
                conn = get_conn()
                conn.execute("UPDATE leads SET stage=? WHERE id=?", (new_stage, lead_id))
                if new_stage == "Selesai" and make_customer and pd.isna(lead["customer_id"]):
                    existing = conn.execute(
                        "SELECT id FROM customers WHERE name=?", (lead["lead_name"],)
                    ).fetchone()
                    if existing:
                        cid = existing["id"]
                    else:
                        cur = conn.execute("""
                            INSERT INTO customers(name, category, pic, phone, address)
                            VALUES (?, ?, '', ?, '')
                        """, (lead["lead_name"], lead["segment"], lead["contact"] or ""))
                        cid = cur.lastrowid
                    conn.execute("UPDATE leads SET customer_id=? WHERE id=?", (cid, lead_id))
                conn.commit()
                conn.close()
                if new_stage == "Selesai":
                    st.success("Proyek selesai. Lanjutkan: daftarkan perangkat di 'Data Perangkat' dan cetak QR di 'QR Aset'.")
                else:
                    st.success("Tahap proyek diperbarui.")
                st.rerun()

# =========================================================
# 8. QR ASET (Slide 8: satu identitas digital untuk setiap perangkat)
# =========================================================
elif menu == "QR Aset":
    st.markdown('<div class="main-title">QR Aset Perangkat</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Satu identitas digital untuk setiap perangkat: tempel QR di perangkat, scan untuk melihat status dan histori.</div>',
        unsafe_allow_html=True
    )

    devices = query_df("""
        SELECT d.device_code, d.device_name, d.device_type, d.location, c.name AS customer_name
        FROM devices d JOIN customers c ON c.id = d.customer_id
        ORDER BY c.name, d.device_code
    """)

    if devices.empty:
        st.info("Belum ada perangkat. Tambahkan perangkat terlebih dahulu di menu 'Data Perangkat'.")
    else:
        base_url = st.text_input(
            "URL aplikasi (opsional)",
            value="",
            placeholder="https://alamat-aplikasi-anda.com",
            help="Jika diisi, QR akan membuka halaman detail perangkat di aplikasi ini. "
                 "Jika kosong, QR berisi teks identitas perangkat."
        )
        options = {
            f'{r["device_code"]} - {r["device_name"]} - {r["customer_name"]}': r
            for _, r in devices.iterrows()
        }
        selected = st.selectbox("Pilih Perangkat", list(options.keys()))
        r = options[selected]
        payload = qr_payload(r["device_code"], r["device_name"], r["customer_name"], r["location"], base_url)
        png = qr_png_bytes(payload)

        left, right = st.columns([1, 2])
        with left:
            if png is None:
                st.warning("Paket 'qrcode' belum terpasang. Jalankan: pip install -r requirements.txt")
            else:
                st.image(png, caption=r["device_code"], width=240)
                st.download_button("⬇️ Unduh QR (PNG)", data=png,
                                   file_name=f'QR-{r["device_code"]}.png', mime="image/png")
        with right:
            st.write(f"**Perangkat:** {r['device_name']} ({r['device_type']})")
            st.write(f"**Pelanggan:** {r['customer_name']}")
            st.write(f"**Lokasi:** {r['location'] or '-'}")
            st.caption("Isi QR:")
            st.code(payload, language=None)

        if png is not None and st.checkbox("Siapkan ZIP QR untuk semua perangkat"):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for _, d in devices.iterrows():
                    data = qr_png_bytes(qr_payload(d["device_code"], d["device_name"],
                                                   d["customer_name"], d["location"], base_url))
                    zf.writestr(f'QR-{d["device_code"]}.png', data)
            st.download_button("⬇️ Unduh ZIP semua QR", data=buf.getvalue(),
                               file_name="QR-semua-perangkat.zip", mime="application/zip")

# =========================================================
# 9. KONTRAK AMC & SUBSCRIPTION (Slide 6: recurring revenue)
# =========================================================
elif menu == "Kontrak & Subscription":
    st.markdown('<div class="main-title">Kontrak AMC & Subscription</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Mesin pendapatan berulang: Annual Maintenance Contract (AMC) dan Subscription MSN SmartCare.</div>',
        unsafe_allow_html=True
    )

    customers = query_df("SELECT id, name FROM customers ORDER BY name")
    customer_map = dict(zip(customers["name"], customers["id"])) if not customers.empty else {}

    contracts = query_df("""
        SELECT k.*, c.name AS customer_name
        FROM contracts k JOIN customers c ON c.id = k.customer_id
        ORDER BY k.id DESC
    """)

    if not contracts.empty:
        contracts["end_date"] = contracts.apply(
            lambda r: (pd.Timestamp(r["start_date"]) + pd.DateOffset(months=int(r["duration_months"]))).date(), axis=1
        )
        contracts["sisa_hari"] = contracts["end_date"].apply(lambda d: (d - date.today()).days)

        def effective_status(r):
            if r["status"] != "Aktif":
                return r["status"]
            if r["sisa_hari"] < 0:
                return "Berakhir"
            return "Segera Berakhir" if r["sisa_hari"] <= 30 else "Aktif"

        contracts["status_efektif"] = contracts.apply(effective_status, axis=1)
        active = contracts[contracts["status_efektif"].isin(["Aktif", "Segera Berakhir"])]
        n_active = len(active)
        n_subs = int(active["contract_type"].str.startswith("Subscription").sum())
        recurring = float(active["monthly_fee"].sum())
        n_soon = int((contracts["status_efektif"] == "Segera Berakhir").sum())
    else:
        n_active = n_subs = n_soon = 0
        recurring = 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kontrak Aktif", n_active)
    c2.metric("Subscription Aktif", n_subs)
    c3.metric("Kontribusi Laba Berulang / Bulan", rupiah(recurring))
    c4.metric("Segera Berakhir (≤30 hari)", n_soon)
    st.caption("Pembanding: asumsi business plan = 5 subscription dengan kontribusi laba Rp400.000/klien/bulan (Rp2.000.000/bulan).")

    with st.expander("➕ Tambah Kontrak / Subscription", expanded=False):
        if not customer_map:
            st.warning("Tambahkan pelanggan terlebih dahulu.")
        else:
            with st.form("contract_form"):
                a, b = st.columns(2)
                with a:
                    cust_name = st.selectbox("Pelanggan", list(customer_map.keys()))
                    ctype = st.selectbox("Jenis Layanan", CONTRACT_TYPES)
                    start_date = st.date_input("Tanggal Mulai", value=date.today())
                with b:
                    duration = st.number_input(
                        "Durasi (bulan)", min_value=1, max_value=60, value=12,
                        help="Untuk AMC 6/12 Bulan, durasi otomatis mengikuti jenis layanan."
                    )
                    fee = st.number_input("Kontribusi Laba / Bulan (Rp)", min_value=0, value=400_000, step=50_000)
                    notes = st.text_input("Catatan")
                save_ct = st.form_submit_button("Simpan Kontrak", type="primary")
                if save_ct:
                    months = 6 if ctype == "AMC 6 Bulan" else (12 if ctype == "AMC 12 Bulan" else int(duration))
                    conn = get_conn()
                    conn.execute("""
                        INSERT INTO contracts(customer_id, contract_type, start_date, duration_months,
                                              monthly_fee, status, notes)
                        VALUES (?, ?, ?, ?, ?, 'Aktif', ?)
                    """, (int(customer_map[cust_name]), ctype, str(start_date), months, float(fee), notes.strip()))
                    conn.commit()
                    conn.close()
                    st.success("Kontrak berhasil disimpan.")
                    st.rerun()

    st.subheader("Daftar Kontrak")
    if contracts.empty:
        st.info("Belum ada kontrak.")
    else:
        view = contracts.copy()
        view["monthly_fee"] = view["monthly_fee"].apply(rupiah)
        st.dataframe(
            view[["customer_name", "contract_type", "start_date", "duration_months",
                  "end_date", "sisa_hari", "monthly_fee", "status_efektif", "notes"]],
            use_container_width=True, hide_index=True
        )

        st.subheader("Update Status Kontrak")
        ct_map = {
            f'{r["customer_name"]} - {r["contract_type"]} (mulai {r["start_date"]})': int(r["id"])
            for _, r in contracts.iterrows()
        }
        with st.form("contract_update_form"):
            sel = st.selectbox("Pilih Kontrak", list(ct_map.keys()))
            new_status = st.selectbox("Status Baru", CONTRACT_STATUSES)
            upd = st.form_submit_button("Update Status", type="primary")
            if upd:
                conn = get_conn()
                conn.execute("UPDATE contracts SET status=? WHERE id=?", (new_status, ct_map[sel]))
                conn.commit()
                conn.close()
                st.success("Status kontrak diperbarui.")
                st.rerun()

# =========================================================
# 10. LAPORAN DIGITAL (Slide 8 & 13: laporan digital per pelanggan)
# =========================================================
elif menu == "Laporan Digital":
    st.markdown('<div class="main-title">Laporan Digital</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Histori pekerjaan dan dokumentasi per pelanggan: perangkat, garansi, maintenance, ticket, dan kontrak.</div>',
        unsafe_allow_html=True
    )

    customers = query_df("SELECT id, name, category, pic, phone, address FROM customers ORDER BY name")
    if customers.empty:
        st.info("Belum ada pelanggan.")
    else:
        selected = st.selectbox("Pilih Pelanggan", customers["name"].tolist())
        crow = customers[customers["name"] == selected].iloc[0]
        cid = int(crow["id"])

        devices = enrich_devices(query_df("SELECT * FROM devices WHERE customer_id=? ORDER BY device_code", (cid,)))
        tickets = query_df("""
            SELECT t.ticket_no, t.created_date, d.device_code, t.priority, t.problem,
                   t.status, t.technician, t.resolution, t.closed_date
            FROM tickets t LEFT JOIN devices d ON d.id = t.device_id
            WHERE t.customer_id=? ORDER BY t.id DESC
        """, (cid,))
        logs = query_df("""
            SELECT m.maintenance_date, d.device_code, m.activity, m.technician, m.result
            FROM maintenance_logs m JOIN devices d ON d.id = m.device_id
            WHERE d.customer_id=? ORDER BY m.id DESC
        """, (cid,))
        contracts_c = query_df("""
            SELECT contract_type, start_date, duration_months, monthly_fee, status
            FROM contracts WHERE customer_id=? ORDER BY id DESC
        """, (cid,))

        n_dev = len(devices)
        n_warranty = 0 if devices.empty else int(devices["warranty_status"].isin(["Expired", "Segera Berakhir"]).sum())
        n_maint = 0 if devices.empty else int(devices["maintenance_status"].isin(["Terlambat", "Jatuh Tempo"]).sum())
        n_open = 0 if tickets.empty else int((tickets["status"] != "Closed").sum())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Perangkat", n_dev)
        c2.metric("Garansi Perlu Perhatian", n_warranty)
        c3.metric("Maintenance Perlu Perhatian", n_maint)
        c4.metric("Ticket Aktif", n_open)

        if devices.empty:
            dev_view = pd.DataFrame()
        else:
            dev_view = devices[[
                "device_code", "device_name", "device_type", "location", "install_date",
                "warranty_end", "warranty_status", "last_maintenance", "next_maintenance",
                "maintenance_status", "status"
            ]].rename(columns={
                "device_code": "Kode", "device_name": "Perangkat", "device_type": "Jenis",
                "location": "Lokasi", "install_date": "Instalasi", "warranty_end": "Garansi s/d",
                "warranty_status": "Status Garansi", "last_maintenance": "Maintenance Terakhir",
                "next_maintenance": "Maintenance Berikut", "maintenance_status": "Status Maintenance",
                "status": "Status"
            }).fillna("-")
        tk_view = tickets.rename(columns={
            "ticket_no": "No Ticket", "created_date": "Tanggal", "device_code": "Perangkat",
            "priority": "Prioritas", "problem": "Masalah", "status": "Status",
            "technician": "Teknisi", "resolution": "Solusi", "closed_date": "Ditutup"
        }).fillna("-")
        log_view = logs.rename(columns={
            "maintenance_date": "Tanggal", "device_code": "Perangkat", "activity": "Aktivitas",
            "technician": "Teknisi", "result": "Hasil"
        }).fillna("-")
        ct_view = contracts_c.copy()
        if not ct_view.empty:
            ct_view["monthly_fee"] = ct_view["monthly_fee"].apply(rupiah)
        ct_view = ct_view.rename(columns={
            "contract_type": "Jenis", "start_date": "Mulai", "duration_months": "Durasi (bln)",
            "monthly_fee": "Kontribusi Laba/Bulan", "status": "Status"
        })

        st.subheader("Perangkat, Garansi & Maintenance")
        show_df_or_info(dev_view, "Belum ada perangkat.")
        st.subheader("Riwayat Maintenance")
        show_df_or_info(log_view, "Belum ada riwayat maintenance.")
        st.subheader("Ticket Kerusakan")
        show_df_or_info(tk_view, "Belum ada ticket.")
        st.subheader("Kontrak AMC & Subscription")
        show_df_or_info(ct_view, "Belum ada kontrak.")

        report_html = build_report_html(
            crow, dev_view, tk_view, log_view, ct_view,
            {"Perangkat": n_dev, "Garansi perlu perhatian": n_warranty,
             "Maintenance perlu perhatian": n_maint, "Ticket aktif": n_open}
        )
        d1, d2 = st.columns(2)
        d1.download_button("⬇️ Unduh Laporan (HTML, siap cetak/PDF)", data=report_html.encode("utf-8"),
                           file_name=f"Laporan-{selected.replace(' ', '_')}-{date.today()}.html",
                           mime="text/html")
        if not dev_view.empty:
            d2.download_button("⬇️ Unduh Data Perangkat (CSV)", data=dev_view.to_csv(index=False).encode("utf-8"),
                               file_name=f"Perangkat-{selected.replace(' ', '_')}.csv", mime="text/csv")

# =========================================================
# 5. SIMULASI PENDAPATAN & BEP (Slide 10 & 11)
# =========================================================
elif menu == "Simulasi Pendapatan & BEP":
    st.markdown('<div class="main-title">Simulasi Pendapatan dan BEP</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Simulasi margin satu proyek instalasi CCTV dan proyeksi BEP dengan subscription SmartCare '
        '(bukan data penjualan aktual).</div>',
        unsafe_allow_html=True
    )

    # ---- Slide 10: dasar asumsi margin per proyek
    st.subheader("1. Dasar Asumsi Margin per Proyek (CCTV)")
    m_left, m_right = st.columns(2)
    with m_left:
        selling_price = st.number_input("Harga jual proyek CCTV (Rp)", min_value=0, value=15_000_000, step=500_000)
        cost_device = st.number_input("Perangkat dan material (Rp)", min_value=0, value=7_500_000, step=100_000)
        cost_labor = st.number_input("Tenaga teknisi dan instalasi (Rp)", min_value=0, value=2_000_000, step=100_000)
        cost_other = st.number_input("Transportasi dan biaya variabel lain (Rp)", min_value=0, value=500_000, step=100_000)
    total_variable_cost = cost_device + cost_labor + cost_other
    gross_profit_project = selling_price - total_variable_cost
    with m_right:
        st.metric("Total Biaya Variabel", rupiah(total_variable_cost))
        st.metric("Margin Kontribusi / Proyek", rupiah(gross_profit_project))
        st.caption("Margin kontribusi = Harga jual - total biaya variabel")
        st.caption(f"= {rupiah(selling_price)} - {rupiah(total_variable_cost)} = {rupiah(gross_profit_project)}/proyek")

    st.divider()

    # ---- Slide 11: proyeksi pendapatan & BEP
    st.subheader("2. Proyeksi Pendapatan dan BEP")
    a, b = st.columns(2)
    with a:
        projects_per_month = st.number_input("Jumlah proyek instalasi / bulan", min_value=0, value=2, step=1)
        subscriptions = st.number_input("Jumlah pelanggan subscription SmartCare", min_value=0, value=5, step=1)
        profit_subscription = st.number_input(
            "Kontribusi laba subscription / klien / bulan (Rp)", min_value=0, value=400_000, step=50_000
        )
    with b:
        fixed_cost = st.number_input("Biaya tetap / bulan (Rp)", min_value=0, value=7_000_000, step=100_000)
        initial_investment = st.number_input(
            "Investasi awal prototype (Rp)", min_value=0, value=15_000_000, step=500_000
        )

    project_contribution = projects_per_month * gross_profit_project
    subscription_contribution = subscriptions * profit_subscription
    total_contribution = project_contribution + subscription_contribution
    operating_profit = total_contribution - fixed_cost
    annual_profit = operating_profit * 12

    if gross_profit_project > 0:
        bep_no_subs = fixed_cost / gross_profit_project
        bep_with_subs = max(0, fixed_cost - subscription_contribution) / gross_profit_project
        bep_no_subs_round = math.ceil(round(bep_no_subs, 6))
        bep_with_subs_round = math.ceil(round(bep_with_subs, 6))
    else:
        bep_no_subs = bep_with_subs = bep_no_subs_round = bep_with_subs_round = None

    payback_months = (initial_investment / operating_profit) if operating_profit > 0 else None

    st.markdown("#### Asumsi target awal")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kontribusi Proyek", rupiah(project_contribution))
    c2.metric("Kontribusi Subscription", rupiah(subscription_contribution))
    c3.metric("Total Kontribusi Laba / Bulan", rupiah(total_contribution))
    c4.metric("Estimasi Laba Bersih / Bulan", rupiah(operating_profit))

    st.markdown("#### Perhitungan BEP")
    x1, x2, x3 = st.columns(3)
    if bep_no_subs is not None:
        x1.metric("BEP Tanpa Subscription", f"{num_id(bep_no_subs)} proyek",
                  help="Biaya tetap / margin per proyek.")
        x2.metric("BEP Dengan Subscription", f"{num_id(bep_with_subs)} proyek",
                  help="(Biaya tetap - kontribusi subscription) / margin per proyek.")
        st.caption(
            f"Tanpa subscription: {rupiah(fixed_cost)} / {rupiah(gross_profit_project)} = {num_id(bep_no_subs)} proyek "
            f"-> dibulatkan menjadi {bep_no_subs_round} proyek/bulan. "
            f"Dengan subscription: ({rupiah(fixed_cost)} - {rupiah(subscription_contribution)}) / "
            f"{rupiah(gross_profit_project)} = {num_id(bep_with_subs)} proyek -> {bep_with_subs_round} proyek/bulan."
        )
        if projects_per_month >= bep_with_subs_round:
            st.success(f"Target {projects_per_month} proyek/bulan sudah memenuhi BEP dengan subscription "
                       f"({bep_with_subs_round} proyek/bulan).")
        else:
            st.warning(f"Target {projects_per_month} proyek/bulan masih di bawah BEP dengan subscription "
                       f"({bep_with_subs_round} proyek/bulan).")
    else:
        x1.metric("BEP Tanpa Subscription", "-")
        x2.metric("BEP Dengan Subscription", "-")
        st.warning("Margin per proyek harus lebih dari 0 untuk menghitung BEP.")
    x3.metric("Payback Period", f"{num_id(payback_months)} bulan" if payback_months is not None else "Belum tercapai")

    st.markdown("#### Kesimpulan finansial")
    p1, p2 = st.columns(2)
    p1.metric("Estimasi Laba Tahunan", rupiah(annual_profit),
              help=f"{rupiah(operating_profit)} x 12")
    p2.metric(
        "Status Kelayakan Operasional",
        "Surplus" if operating_profit > 0 else ("BEP" if operating_profit == 0 else "Defisit")
    )
    st.caption("Makna bisnis: subscription membuat cashflow lebih stabil dan mengurangi ketergantungan pada proyek baru.")

    projection = pd.DataFrame({
        "Bulan": list(range(1, 13)),
        "Kontribusi Proyek": [project_contribution] * 12,
        "Kontribusi Subscription": [subscription_contribution] * 12,
        "Biaya Tetap": [fixed_cost] * 12,
        "Laba Operasional": [operating_profit] * 12,
    })
    projection["Laba Kumulatif"] = projection["Laba Operasional"].cumsum()

    st.line_chart(projection.set_index("Bulan")[["Laba Kumulatif"]], use_container_width=True)

    money_cols = [c for c in projection.columns if c != "Bulan"]
    shown = projection.copy()
    shown[money_cols] = shown[money_cols].apply(lambda col: col.map(rupiah))
    st.dataframe(shown, use_container_width=True, hide_index=True)

    st.markdown("### Rumus yang Digunakan")
    st.markdown("""
- **Margin Kontribusi / Proyek** = Harga Jual - Total Biaya Variabel
- **Kontribusi Proyek** = Jumlah Proyek x Margin per Proyek
- **Kontribusi Subscription** = Jumlah Subscription x Kontribusi Laba per Subscription
- **Laba Bersih / Bulan** = Total Kontribusi - Biaya Tetap
- **BEP Tanpa Subscription** = Biaya Tetap / Margin per Proyek
- **BEP Dengan Subscription** = (Biaya Tetap - Kontribusi Subscription) / Margin per Proyek
- **Payback Period** = Investasi Awal / Laba Bersih per Bulan
""")

# =========================================================
# 6. SIMULASI ROE & ROA
# =========================================================
elif menu == "Simulasi ROE & ROA":
    st.markdown('<div class="main-title">ROE dan ROA</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Simulasi rasio profitabilitas untuk menilai efisiensi modal dan aset MSN SmartCare.</div>',
        unsafe_allow_html=True
    )

    col_data, col_roe, col_roa = st.columns(3)

    with col_data:
        with st.container(border=True):
            st.markdown('<div class="ratio-label">Data Simulasi</div>', unsafe_allow_html=True)
            net_profit = st.number_input(
                "Laba bersih tahunan (Rp)", min_value=0, value=60_000_000, step=1_000_000
            )
            equity = st.number_input(
                "Modal sendiri (Rp)", min_value=0, value=62_500_000, step=500_000
            )
            total_assets = st.number_input(
                "Total aset operasional (Rp)", min_value=0, value=75_000_000, step=500_000
            )
            st.caption(
                "Angka digunakan untuk simulasi business plan dan bisa disesuaikan dengan kondisi riil."
            )

    roe = (net_profit / equity * 100) if equity > 0 else None
    roa = (net_profit / total_assets * 100) if total_assets > 0 else None

    with col_roe:
        if roe is None:
            roe_value, roe_desc = "-", "Modal sendiri harus lebih dari 0 untuk menghitung ROE."
        else:
            roe_value = pct_id(roe)
            roe_desc = (
                f"setiap Rp1 modal sendiri yang ditanamkan pada MSN SmartCare menghasilkan "
                f"Rp{num_id(roe / 100)} laba bersih dalam satu tahun.<br>"
                f"ROE sebesar {pct_id(roe)} menunjukkan potensi pengembalian modal "
                f"berdasarkan asumsi bisnis tersebut. Namun, angka ini merupakan proyeksi, "
                f"bukan jaminan bahwa modal akan kembali dalam satu tahun."
            )
        st.markdown(f"""
<div class="ratio-card ratio-light">
    <div class="ratio-label">Return on Equity</div>
    <div class="ratio-name">ROE</div>
    <div class="ratio-section"><b>Rumus:</b><br>ROE = Laba Bersih / Modal Sendiri × 100%</div>
    <div class="ratio-section"><b>Perhitungan:</b><br>{rupiah(net_profit)} / {rupiah(equity)} × 100%</div>
    <div class="ratio-value">{roe_value}</div>
    <div class="ratio-desc">{roe_desc}</div>
</div>
""", unsafe_allow_html=True)

    with col_roa:
        if roa is None:
            roa_value, roa_desc = "-", "Total aset harus lebih dari 0 untuk menghitung ROA."
        else:
            roa_value = pct_id(roa)
            if roa >= 20:
                roa_desc = "aset operasional digunakan sangat produktif untuk menghasilkan laba"
            elif roa >= 5:
                roa_desc = "aset operasional digunakan cukup produktif untuk menghasilkan laba"
            else:
                roa_desc = "aset operasional belum terlalu produktif untuk menghasilkan laba"
        st.markdown(f"""
<div class="ratio-card ratio-dark">
    <div class="ratio-label">Return on Assets</div>
    <div class="ratio-name">ROA</div>
    <div class="ratio-section"><b>Rumus:</b><br>ROA = Laba Bersih / Total Aset × 100%</div>
    <div class="ratio-section"><b>Perhitungan:</b><br>{rupiah(net_profit)} / {rupiah(total_assets)} × 100%</div>
    <div class="ratio-value">{roa_value}</div>
    <div class="ratio-desc">{roa_desc}</div>
</div>
""", unsafe_allow_html=True)

    st.markdown(
        '<div class="interpretation-box">Interpretasi: semakin tinggi ROE dan ROA, '
        'semakin efisien bisnis menggunakan modal dan aset.</div>',
        unsafe_allow_html=True
    )
    st.caption("MSN SmartCare | Business Plan Technopreneur")

# =========================================================
# 11. RENCANA INVESTASI & ROADMAP (Slide 16, 22, 23, 24)
# =========================================================
elif menu == "Rencana Investasi":
    st.markdown('<div class="main-title">Rencana Investasi</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Skenario kebutuhan dana, skema kerja sama investor, dan roadmap implementasi - '
        'angka indikatif untuk diskusi dengan calon investor.</div>',
        unsafe_allow_html=True
    )

    tab_dana, tab_kerja, tab_simulasi, tab_road = st.tabs(["Penggunaan Dana", "Kerja Sama Investor", "Simulasi Keuntungan & Pengembalian", "Roadmap Implementasi"])

    with tab_dana:
        total_fund = st.number_input("Usulan pendanaan (Rp)", min_value=0, value=50_000_000, step=1_000_000)
        allocations = [
            ("Pengembangan platform", 40, "Pengembangan prototype, dashboard, QR aset dan ticketing"),
            ("Pemasaran B2B", 30, "Pemasaran B2B, website, presentasi dan pilot project"),
            ("Operasional", 20, "Kebutuhan operasional, perangkat pendukung dan teknisi"),
            ("SOP & cadangan", 10, "Penyusunan SOP, pelatihan dan cadangan implementasi"),
        ]
        left, right = st.columns(2)
        pcts = []
        with left:
            for label, default_pct, _ in allocations:
                pcts.append(st.number_input(f"{label} (%)", min_value=0, max_value=100, value=default_pct, step=5))
        total_pct = sum(pcts)
        alloc_df = pd.DataFrame({
            "Komponen": [a[0] for a in allocations],
            "Persentase": pcts,
            "Nilai (Rp)": [total_fund * p / 100 for p in pcts],
            "Keterangan": [a[2] for a in allocations],
        })
        with right:
            st.metric("Total Alokasi", f"{total_pct}%")
            if total_pct != 100:
                st.warning(f"Total alokasi {total_pct}%, seharusnya 100%.")
            st.bar_chart(alloc_df.set_index("Komponen")[["Nilai (Rp)"]])

        shown = alloc_df.copy()
        shown["Persentase"] = shown["Persentase"].map(lambda p: f"{p}%")
        shown["Nilai (Rp)"] = shown["Nilai (Rp)"].map(rupiah)
        st.dataframe(shown, use_container_width=True, hide_index=True)
        st.caption(
            "Catatan: kebutuhan dana dan alokasi di atas adalah skenario usulan, bukan pendanaan yang telah diperoleh."
        )

    with tab_kerja:
        k1, k2, k3 = st.columns(3)
        with k1:
            with st.container(border=True):
                st.markdown("**1. Kontribusi investor**")
                st.write("Investor menyediakan pendanaan sesuai kesepakatan. Contoh kebutuhan awal Rp50 juta "
                         "untuk pengembangan platform dan ekspansi pasar.")
        with k2:
            with st.container(border=True):
                st.markdown("**2. Pelaksanaan bisnis**")
                st.write("Dana digunakan bertahap untuk platform, pemasaran B2B, operasional, dan SOP. "
                         "Kemajuan dipantau melalui target proyek dan subscription.")
        with k3:
            with st.container(border=True):
                st.markdown("**3. Evaluasi & imbal hasil**")
                st.write("Investor menerima laporan keuangan dan kinerja berkala. Skema bagi hasil atau "
                         "kepemilikan dibahas berdasarkan hasil uji kelayakan.")
        st.markdown("#### Cara bergabung")
        st.write("Diskusi proposal -> evaluasi proyeksi dan risiko -> kesepakatan tertulis mengenai modal, "
                 "hak, dan kewajiban.")
        st.info("Tujuan bersama: memperbanyak proyek, meningkatkan pelanggan berlangganan, dan membangun "
                "pendapatan berulang. Rp50 juta adalah simulasi kebutuhan dana; keuntungan dan pengembalian "
                "modal tidak dijamin.")

    with tab_simulasi:
        st.markdown("#### Simulasi Keuntungan & Pengembalian Modal Investor")
        st.caption(
            "Skema Principal First: 20% laba bersih aktual disisihkan sebagai cadangan kas. "
            "Dari 80% sisanya, porsi investor adalah 25% untuk investasi di bawah Rp50 juta "
            "atau 50% untuk investasi Rp50 juta ke atas. Selama pokok belum lunas, seluruh "
            "alokasi investor digunakan untuk mengembalikan pokok. Setelah lunas, alokasi "
            "investor menjadi bagi hasil lanjutan sesuai durasi perjanjian."
        )

        sim_a, sim_b, sim_c = st.columns(3)
        with sim_a:
            investment = st.number_input(
                "Nilai investasi (Rp)", min_value=1_000_000, value=50_000_000,
                step=1_000_000, key="inv_sim_modal_v2"
            )
            base_monthly_profit = st.number_input(
                "Laba bersih acuan per bulan (Rp)", min_value=0, value=5_000_000,
                step=500_000, key="inv_sim_profit_v2",
                help="Nilai awal untuk mengisi tabel. Anda dapat mengubah laba bersih setiap bulan pada tabel aktual di bawah."
            )
        with sim_b:
            post_return_months = st.number_input(
                "Durasi bagi hasil setelah modal kembali (bulan)", min_value=0,
                max_value=120, value=24, step=1, key="inv_sim_post_months_v2"
            )
            max_sim_months = st.number_input(
                "Batas periode simulasi (bulan)", min_value=12, max_value=120,
                value=60, step=12, key="inv_sim_horizon_v2"
            )
        # Default porsi investor mengikuti tier investasi sebelumnya, tetapi pengguna
        # dapat mengubahnya. Slider diterapkan pada laba setelah cadangan kas.
        default_investor_pct = 50 if investment >= 50_000_000 else 25
        with st.expander("Atur parameter bagi hasil dan cadangan kas", expanded=True):
            param_a, param_b = st.columns(2)
            with param_a:
                investor_share_pct = st.slider(
                    "Porsi investor dari laba setelah cadangan (%)",
                    min_value=0, max_value=100, value=int(default_investor_pct), step=1,
                    key="inv_sim_share_pct_v3",
                    help="Nilai awal 25% untuk investasi di bawah Rp50 juta dan 50% untuk investasi Rp50 juta ke atas. Anda bebas mengubahnya."
                )
            with param_b:
                reserve_pct = st.slider(
                    "Cadangan kas dari laba bersih (%)",
                    min_value=0, max_value=80, value=20, step=1,
                    key="inv_sim_reserve_pct_v3",
                    help="Persentase laba bersih positif yang ditahan sebagai cadangan perusahaan."
                )
        investor_share_rate = investor_share_pct / 100
        reserve_rate = reserve_pct / 100
        distributable_rate = 1 - reserve_rate
        st.caption(
            f"Parameter aktif: cadangan kas {reserve_pct}% dari laba bersih positif; "
            f"investor menerima {investor_share_pct}% dari laba setelah cadangan. "
            f"Bagian perusahaan dari laba setelah cadangan adalah {100-investor_share_pct}%."
        )

        st.markdown("#### Input laba bersih aktual per bulan")
        st.info(
            "Masukkan laba bersih aktual/proyeksi untuk setiap bulan. Jika pada pertengahan bulan "
            "target belum tercapai, cukup perbarui nilai bulan tersebut setelah tutup buku. "
            "Nilai negatif menunjukkan rugi; tidak ada pembagian atau pengembalian pokok pada bulan rugi."
        )
        if "inv_sim_monthly_actual_v2" not in st.session_state or len(st.session_state["inv_sim_monthly_actual_v2"]) != int(max_sim_months):
            st.session_state["inv_sim_monthly_actual_v2"] = pd.DataFrame({
                "Bulan": list(range(1, int(max_sim_months) + 1)),
                "Laba Bersih Aktual (Rp)": [int(base_monthly_profit)] * int(max_sim_months),
            })
        else:
            # Keep user-edited monthly figures; only ensure month labels match the selected horizon.
            st.session_state["inv_sim_monthly_actual_v2"]["Bulan"] = list(range(1, int(max_sim_months) + 1))

        actual_input_df = st.data_editor(
            st.session_state["inv_sim_monthly_actual_v2"],
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="inv_sim_actual_editor_v2",
            column_config={
                "Bulan": st.column_config.NumberColumn("Bulan", disabled=True, format="%d"),
                "Laba Bersih Aktual (Rp)": st.column_config.NumberColumn(
                    "Laba Bersih Aktual (Rp)", min_value=-1_000_000_000,
                    max_value=10_000_000_000, step=100_000, format="Rp %d"
                ),
            },
        )
        st.session_state["inv_sim_monthly_actual_v2"] = actual_input_df.copy()

        schedule = []
        principal_remaining = float(investment)
        cumulative_to_investor = 0.0
        cumulative_reserve = 0.0
        post_month_count = 0
        recovered_at = None
        total_investor_principal = 0.0
        total_investor_profit = 0.0

        for _, actual_row in actual_input_df.iterrows():
            month = int(actual_row["Bulan"])
            net_profit = float(actual_row["Laba Bersih Aktual (Rp)"])
            reserve_amount = max(net_profit, 0.0) * reserve_rate
            distributable_profit = max(net_profit, 0.0) - reserve_amount
            investor_pool = distributable_profit * investor_share_rate
            repayment = 0.0
            profit_share = 0.0

            if net_profit <= 0:
                phase = "Rugi / tidak ada pembagian"
            elif principal_remaining > 0 and investor_pool > 0:
                repayment = min(principal_remaining, investor_pool)
                principal_remaining -= repayment
                total_investor_principal += repayment
                phase = "Pengembalian pokok"
                if principal_remaining <= 0.005:
                    principal_remaining = 0.0
                    recovered_at = month
            elif principal_remaining <= 0 and post_month_count < int(post_return_months):
                profit_share = investor_pool
                total_investor_profit += profit_share
                post_month_count += 1
                phase = "Bagi hasil setelah pokok kembali"
            elif principal_remaining <= 0:
                phase = "Masa bagi hasil selesai"
            else:
                phase = "Laba tersedia, menunggu alokasi"

            investor_received = repayment + profit_share
            cumulative_to_investor += investor_received
            cumulative_reserve += reserve_amount
            company_share = max(distributable_profit - investor_pool, 0.0)
            schedule.append({
                "Bulan": month,
                "Laba Bersih Aktual (Rp)": net_profit,
                f"Cadangan Kas {reserve_pct}% (Rp)": reserve_amount,
                "Laba Setelah Cadangan (Rp)": distributable_profit,
                "Porsi Investor (Rp)": investor_pool,
                "Pengembalian Pokok (Rp)": repayment,
                "Bagi Hasil Investor (Rp)": profit_share,
                "Bagian Perusahaan (Rp)": company_share,
                "Sisa Pokok (Rp)": principal_remaining,
                "Akumulasi Diterima Investor (Rp)": cumulative_to_investor,
                "Tahap": phase,
            })

        schedule_df = pd.DataFrame(schedule)
        total_actual_profit = float(actual_input_df["Laba Bersih Aktual (Rp)"].sum())
        total_reserve = float(schedule_df["Cadangan Kas 20% (Rp)"].sum())
        total_received = float(schedule_df["Pengembalian Pokok (Rp)"].sum() + schedule_df["Bagi Hasil Investor (Rp)"].sum())
        average_positive_profit = float(actual_input_df.loc[actual_input_df["Laba Bersih Aktual (Rp)"] > 0, "Laba Bersih Aktual (Rp)"].mean()) if (actual_input_df["Laba Bersih Aktual (Rp)"] > 0).any() else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Investasi", rupiah(investment))
        k2.metric("Porsi investor", f"{investor_share_pct}%")
        k3.metric("Cadangan kas terkumpul", rupiah(total_reserve))
        k4.metric("Total diterima investor", rupiah(total_received))

        r1, r2, r3 = st.columns(3)
        r1.metric("Pokok yang sudah kembali", rupiah(total_investor_principal))
        r2.metric("Sisa pokok investasi", rupiah(principal_remaining))
        r3.metric("Keuntungan pasca-pokok", rupiah(total_investor_profit))

        if recovered_at is not None:
            st.success(f"Pokok investasi diproyeksikan kembali pada bulan ke-{recovered_at} berdasarkan input laba bulanan.")
        else:
            st.warning("Pokok investasi belum kembali dalam periode simulasi berdasarkan laba aktual/proyeksi yang dimasukkan.")
        st.caption(
            f"Rumus: cadangan = {reserve_pct}% × laba bersih positif; laba setelah cadangan = {100-reserve_pct}%; "
            f"alokasi investor = {investor_share_pct}% × laba setelah cadangan. "
            "Pada bulan rugi atau laba nol, cadangan dan pembayaran investor adalah Rp0."
        )

        st.markdown("#### Proyeksi arus kas dan pengembalian per bulan")
        if not schedule_df.empty:
            chart_df = schedule_df.set_index("Bulan")[["Akumulasi Diterima Investor (Rp)", "Sisa Pokok (Rp)"]]
            st.line_chart(chart_df, use_container_width=True)
            display_schedule = schedule_df.copy()
            money_cols = [c for c in display_schedule.columns if c.endswith("(Rp)")]
            for col in money_cols:
                display_schedule[col] = display_schedule[col].map(rupiah)
            st.dataframe(display_schedule, use_container_width=True, hide_index=True)
            st.download_button(
                "Unduh proyeksi arus pengembalian (CSV)",
                data=schedule_df.to_csv(index=False).encode("utf-8-sig"),
                file_name="simulasi_pengembalian_principal_first_msn_smartcare.csv",
                mime="text/csv",
            )

        st.markdown("#### Ringkasan asumsi dan sensitivitas")
        st.caption("Sensitivitas memakai rata-rata laba positif dari tabel bulanan; ini hanya pembanding, bukan jaminan.")
        sensitivity_rows = []
        for label, factor in [("Konservatif (-40%)", 0.6), ("Dasar", 1.0), ("Optimistis (+40%)", 1.4)]:
            case_profit = average_positive_profit * factor
            monthly_investor_pool = case_profit * distributable_rate * investor_share_rate
            months_case = math.ceil(investment / monthly_investor_pool) if monthly_investor_pool > 0 else None
            sensitivity_rows.append({
                "Skenario": label,
                "Rata-rata Laba Bersih/Bulan": rupiah(case_profit),
                f"Cadangan Kas {reserve_pct}%": rupiah(case_profit * reserve_rate),
                "Alokasi Investor/Bulan": rupiah(monthly_investor_pool),
                "Estimasi Bulan Pengembalian": months_case if months_case is not None else "Tidak terhitung",
            })
        st.dataframe(pd.DataFrame(sensitivity_rows), use_container_width=True, hide_index=True)

        st.warning(
            "Penting: simulasi menggunakan laba bersih aktual/proyeksi yang diinput per bulan. "
            f"Cadangan kas {reserve_pct}% dihitung dari laba bersih positif. Pembayaran investor tidak dijamin "
            "dan hanya dilakukan jika laba tersedia serta kondisi kas memungkinkan. Definisi laba bersih, "
            "perlakuan kerugian, prioritas pengembalian pokok, durasi bagi hasil lanjutan, dan mekanisme "
            "keluar harus disepakati dalam perjanjian tertulis."
        )

    with tab_road:
        phases = [
            ("0-3 Bulan", "Prototype SmartCare, katalog digital, database aset sederhana"),
            ("4-6 Bulan", "Pilot project pada 3-5 pelanggan, SOP ticketing, QR aset"),
            ("7-9 Bulan", "Paket subscription, dashboard laporan, integrasi WA reminder"),
            ("10-12 Bulan", "Ekspansi pasar institusi, rekrut teknisi mitra, evaluasi BEP"),
        ]
        for col, (period, desc) in zip(st.columns(4), phases):
            with col:
                with st.container(border=True):
                    st.markdown(f"**{period}**")
                    st.write(desc)

# =========================================================
# DATA PELANGGAN
# =========================================================
elif menu == "Data Pelanggan":
    st.markdown('<div class="main-title">Data Pelanggan</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Master pelanggan MSN SmartCare.</div>', unsafe_allow_html=True)

    with st.expander("➕ Tambah Pelanggan", expanded=False):
        with st.form("customer_form"):
            name = st.text_input("Nama Pelanggan")
            category = st.selectbox("Kategori", CUSTOMER_CATEGORIES)
            pic = st.text_input("PIC")
            phone = st.text_input("Telepon / WhatsApp")
            address = st.text_area("Alamat")
            add = st.form_submit_button("Simpan Pelanggan", type="primary")

            if add:
                if not name.strip():
                    st.error("Nama pelanggan wajib diisi.")
                else:
                    conn = get_conn()
                    conn.execute("""
                        INSERT INTO customers(name, category, pic, phone, address)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        name.strip(), category, pic.strip(),
                        phone.strip(), address.strip()
                    ))
                    conn.commit()
                    conn.close()
                    st.success("Pelanggan berhasil ditambahkan.")
                    st.rerun()

    df = query_df("SELECT id, name, category, pic, phone, address, created_at FROM customers ORDER BY id DESC")
    st.dataframe(df, use_container_width=True, hide_index=True)

# -----------------------------
# Footer
# -----------------------------
st.divider()
st.caption("Prototype Technopreneur - MSN SmartCare | CV Mitra Solution Network")
