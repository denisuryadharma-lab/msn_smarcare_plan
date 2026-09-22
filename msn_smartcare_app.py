
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
# 5. Simulasi pendapatan dan BEP
# =========================================================

APP_TITLE = "MSN SmartCare"
DB_PATH = Path("msn_smartcare.db")

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
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

    conn.commit()
    seed_data(conn)
    conn.close()

def seed_data(conn):
    cur = conn.cursor()
    count = cur.execute("SELECT COUNT(*) AS n FROM customers").fetchone()["n"]
    if count > 0:
        return

    customers = [
        ("Universitas Contoh", "Kampus", "Budi Santoso", "0812-1111-2222", "Jakarta"),
        ("PT Graha Digital", "Perkantoran", "Siti Rahma", "0813-3333-4444", "Tangerang"),
        ("Cluster Harmoni", "Perumahan", "Andi Pratama", "0815-5555-6666", "Tangerang"),
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
    # Approximation by months using pandas offset
    return (pd.Timestamp(d) + pd.DateOffset(months=int(months))).date()

def maintenance_due(last_maintenance, install_date, interval_days):
    base = pd.to_datetime(last_maintenance if last_maintenance else install_date).date()
    return base + timedelta(days=int(interval_days))

def get_warranty_status(install_date, months):
    end = warranty_end(install_date, months)
    delta = (end - date.today()).days
    if delta < 0:
        return "Expired"
    elif delta <= 30:
        return "Segera Berakhir"
    return "Aktif"

def get_maintenance_status(last_maintenance, install_date, interval_days):
    due = maintenance_due(last_maintenance, install_date, interval_days)
    delta = (due - date.today()).days
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
</style>
""", unsafe_allow_html=True)

# -----------------------------
# App start
# -----------------------------
init_db()

st.sidebar.title("MSN SmartCare")
st.sidebar.caption("CV Mitra Solution Network")
menu = st.sidebar.radio(
    "Menu",
    [
        "Dashboard",
        "Data Perangkat",
        "Garansi & Maintenance",
        "Ticket Kerusakan",
        "Simulasi Pendapatan & BEP",
        "Data Pelanggan"
    ]
)

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
    st.markdown('<div class="sub-title">CCTV, PABX, dan Roller Blind yang terpasang pada pelanggan.</div>', unsafe_allow_html=True)

    customers = query_df("SELECT id, name FROM customers ORDER BY name")
    customer_map = dict(zip(customers["name"], customers["id"])) if not customers.empty else {}

    with st.expander("➕ Tambah Perangkat Baru", expanded=False):
        with st.form("form_add_device"):
            col1, col2 = st.columns(2)

            with col1:
                customer_name = st.selectbox("Pelanggan", list(customer_map.keys()))
                device_code = st.text_input("Kode Perangkat", placeholder="Contoh: CCTV-010")
                device_name = st.text_input("Nama Perangkat", placeholder="Contoh: CCTV Lobby Utama")
                device_type = st.selectbox("Jenis Perangkat", ["CCTV", "PABX", "Roller Blind"])
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
# 5. SIMULASI PENDAPATAN & BEP
# =========================================================
elif menu == "Simulasi Pendapatan & BEP":
    st.markdown('<div class="main-title">Simulasi Pendapatan dan BEP</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Simulasi awal mengikuti konsep Business Plan MSN SmartCare: proyek instalasi + subscription.</div>',
        unsafe_allow_html=True
    )

    st.info(
        "Nilai default mengikuti simulasi business plan: 2 proyek/bulan, "
        "laba kotor per proyek Rp3.500.000, 5 subscription, laba subscription "
        "Rp400.000/klien/bulan, biaya tetap Rp5.000.000/bulan, dan investasi awal Rp15.000.000."
    )

    with st.form("bep_form"):
        a, b = st.columns(2)

        with a:
            projects_per_month = st.number_input(
                "Jumlah proyek instalasi / bulan", min_value=0, value=2, step=1
            )
            gross_profit_project = st.number_input(
                "Kontribusi laba kotor / proyek (Rp)",
                min_value=0, value=3_500_000, step=100_000
            )
            subscriptions = st.number_input(
                "Jumlah pelanggan subscription", min_value=0, value=5, step=1
            )

        with b:
            profit_subscription = st.number_input(
                "Kontribusi laba subscription / klien / bulan (Rp)",
                min_value=0, value=400_000, step=50_000
            )
            fixed_cost = st.number_input(
                "Biaya tetap / bulan (Rp)",
                min_value=0, value=5_000_000, step=100_000
            )
            initial_investment = st.number_input(
                "Investasi awal prototype & branding (Rp)",
                min_value=0, value=15_000_000, step=500_000
            )

        calc = st.form_submit_button("Hitung Simulasi", type="primary")

    # Calculations always shown
    project_contribution = projects_per_month * gross_profit_project
    subscription_contribution = subscriptions * profit_subscription
    total_contribution = project_contribution + subscription_contribution
    operating_profit = total_contribution - fixed_cost
    annual_profit = operating_profit * 12

    if gross_profit_project > 0:
        bep_projects_without_subs = fixed_cost / gross_profit_project
        remaining_fixed = max(0, fixed_cost - subscription_contribution)
        bep_projects_with_subs = remaining_fixed / gross_profit_project
    else:
        bep_projects_without_subs = None
        bep_projects_with_subs = None

    if operating_profit > 0:
        payback_months = initial_investment / operating_profit
    else:
        payback_months = None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kontribusi Proyek", rupiah(project_contribution))
    c2.metric("Kontribusi Subscription", rupiah(subscription_contribution))
    c3.metric("Total Kontribusi", rupiah(total_contribution))
    c4.metric("Estimasi Laba Operasional/Bulan", rupiah(operating_profit))

    st.subheader("Hasil BEP")

    x1, x2, x3 = st.columns(3)

    if bep_projects_without_subs is not None:
        x1.metric(
            "BEP Tanpa Subscription",
            f"{bep_projects_without_subs:.2f} proyek",
            help="Biaya tetap dibagi kontribusi laba per proyek."
        )
        x2.metric(
            "BEP Dengan Subscription",
            f"{bep_projects_with_subs:.2f} proyek",
            help="Biaya tetap dikurangi kontribusi subscription, kemudian dibagi kontribusi laba per proyek."
        )
    else:
        x1.metric("BEP Tanpa Subscription", "-")
        x2.metric("BEP Dengan Subscription", "-")

    x3.metric(
        "Payback Period",
        f"{payback_months:.2f} bulan" if payback_months is not None else "Belum tercapai"
    )

    st.subheader("Proyeksi Tahunan")
    p1, p2 = st.columns(2)
    p1.metric("Estimasi Laba Tahunan", rupiah(annual_profit))
    p2.metric(
        "Status Kelayakan Operasional",
        "Surplus" if operating_profit > 0 else ("BEP" if operating_profit == 0 else "Defisit")
    )

    projection = pd.DataFrame({
        "Bulan": list(range(1, 13)),
        "Kontribusi Proyek": [project_contribution] * 12,
        "Kontribusi Subscription": [subscription_contribution] * 12,
        "Biaya Tetap": [fixed_cost] * 12,
        "Laba Operasional": [operating_profit] * 12,
    })
    projection["Laba Kumulatif"] = projection["Laba Operasional"].cumsum()

    st.line_chart(
        projection.set_index("Bulan")[["Laba Kumulatif"]],
        use_container_width=True
    )

    st.dataframe(
        projection.applymap(lambda x: rupiah(x) if isinstance(x, (int, float)) else x),
        use_container_width=True,
        hide_index=True
    )

    st.markdown("### Rumus yang Digunakan")
    st.markdown("""
- **Kontribusi Proyek** = Jumlah Proyek × Laba Kotor per Proyek
- **Kontribusi Subscription** = Jumlah Subscription × Laba per Subscription
- **Laba Operasional** = Total Kontribusi − Biaya Tetap
- **BEP Proyek** = Biaya Tetap ÷ Kontribusi Laba per Proyek
- **BEP Proyek dengan Subscription** = (Biaya Tetap − Kontribusi Subscription) ÷ Kontribusi Laba per Proyek
- **Payback Period** = Investasi Awal ÷ Laba Operasional per Bulan
""")

# =========================================================
# DATA PELANGGAN
# =========================================================
elif menu == "Data Pelanggan":
    st.markdown('<div class="main-title">Data Pelanggan</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Master pelanggan MSN SmartCare.</div>', unsafe_allow_html=True)

    with st.expander("➕ Tambah Pelanggan", expanded=False):
        with st.form("customer_form"):
            name = st.text_input("Nama Pelanggan")
            category = st.selectbox(
                "Kategori",
                ["Kampus/Sekolah", "Perkantoran", "Ruko", "Perumahan", "Klinik/Rumah Sakit", "Lainnya"]
            )
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
st.sidebar.divider()
st.sidebar.caption("Prototype Technopreneur - MSN SmartCare")
st.sidebar.caption("CV Mitra Solution Network")
