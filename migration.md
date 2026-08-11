# 📘 Migrasi SQLite → PostgreSQL + Deploy di Droidspaces + Cloudflare Tunnel

## 1. Analisis Mendalam: File Apa Saja yang Terpengaruh?

### File yang HARUS diubah

| File | Alasan Perubahan |
|------|------------------|
| **`src/idx_bandarmology/config.py`** | Menghapus `DB_PATH` (SQLite file path) dan menambahkan `DATABASE_URL` + variabel PostgreSQL |
| **`src/idx_bandarmology/storage.py`** | Seluruh engine database diganti: `sqlite3` → `psycopg2`, schema disesuaikan tipe data PostgreSQL, parameter placeholder `?` → `%s`, upsert tetap pakai `ON CONFLICT` (PostgreSQL 9.5+ native) |
| **`requirements.txt`** | Menambahkan `psycopg2-binary>=2.9` |
| **`.env.example`** | Menambahkan variabel koneksi PostgreSQL |

### File yang TIDAK PERLU diubah (zero-touch)

| File | Kenapa tidak perlu diubah |
|------|---------------------------|
| `analysis.py` | Hanya memanggil `storage.read_prices()`, `storage.read_broker_flow()`, `storage.read_broker_activity()` — signature publik identik |
| `broker_api.py` | Pure API client, tidak ada interaksi DB |
| `pipeline.py` | Hanya memanggil `storage.upsert_*`, `storage.init_db()`, `storage.log_run()` — signature identik |
| `features.py` | Hanya memanggil `storage.read_*` |
| `modeling.py` | Pure ML/stats, tidak ada DB |
| `prices.py` | Pure yfinance client |
| `dashboard/app.py` + semua views | Hanya memanggil `storage.read_*` dan `analysis.*` — tidak ada SQL inline |

### Perubahan Teknis Kunci di `storage.py`

| Aspek | SQLite (lama) | PostgreSQL (baru) |
|-------|---------------|-------------------|
| Driver | `sqlite3` | `psycopg2` |
| Connection | `sqlite3.connect(config.DB_PATH)` | `psycopg2.connect(config.DATABASE_URL)` |
| Date storage | `TEXT` (string ISO) | `DATE` (native) |
| Numeric | `REAL` | `NUMERIC` |
| Placeholder | `?` | `%s` |
| Bulk insert | `executemany` | `execute_values` (dari `psycopg2.extras`, jauh lebih cepat) |
| IN clause | `WHERE ticker IN (?,?,?)` | `WHERE ticker = ANY(%s)` dengan list parameter |
| Auto-init | `init_db()` membuat file `.sqlite` | `init_db()` membuat tabel & index di PostgreSQL |

---

## 2. Step-by-Step: Setup di Droidspaces (Debian on Android)

### Prerequisites
- Droidspaces sudah terinstall dan Debian sudah berjalan
- Akses root/sudo di dalam Debian
- Domain sudah pointing ke Cloudflare (untuk tunnel nanti)

### Step 2.1 — Install PostgreSQL di Debian

```bash
# Masuk ke Debian Droidspaces
proot-distro login debian
# atau sesuai cara login kamu

# Update & install PostgreSQL
sudo apt update
sudo apt install -y postgresql postgresql-contrib postgresql-client

# Start PostgreSQL service
sudo service postgresql start
# Kalau `service` tidak ada di proot, start manual:
# sudo pg_ctlcluster 15 main start
# atau
# sudo -u postgres pg_ctl -D /var/lib/postgresql/15/main start
```

### Step 2.2 — Buat Database & User

```bash
# Switch ke user postgres
sudo -u postgres psql

# Di dalam psql:
CREATE USER bandar WITH PASSWORD 'bandar123';
CREATE DATABASE bandarmology OWNER bandar;
GRANT ALL PRIVILEGES ON DATABASE bandarmology TO bandar;
\q
```

### Step 2.3 — Install Python & Dependencies

```bash
# Install Python & venv
sudo apt install -y python3 python3-venv python3-pip build-essential libpq-dev

# Masuk ke project folder
cd ~/idx-bandarmology

# Buat virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install requirements
pip install --upgrade pip
pip install -r requirements.txt

# Install driver PostgreSQL
pip install psycopg2-binary
```

### Step 2.4 — Konfigurasi `.env`

```bash
cp .env.example .env
nano .env
```

Isi minimal:
```env
BROKER_API_TOKEN=your_stockbit_token_here
DATABASE_URL=postgresql://bandar:bandar123@localhost:5432/bandarmology
```

### Step 2.5 — Test Koneksi & Inisialisasi Tabel

```bash
python3 -c "from idx_bandarmology import storage; storage.init_db(); print('PostgreSQL OK, tables ready')"
```

Kalau sukses, tabel `prices`, `broker_flow`, `broker_activity`, dan `runs` sudah terbuat otomatis dengan index.

### Step 2.6 — Jalankan Pipeline Pertama

```bash
python3 -c "from idx_bandarmology import pipeline; pipeline.run()"
```

Atau dari notebook:
```python
from idx_bandarmology import pipeline
pipeline.run()
```

---

## 3. Step-by-Step: Streamlit di Droidspaces

### Step 3.1 — Install Streamlit

Sudah termasuk di `requirements.txt`, tapi pastikan:
```bash
pip install streamlit>=1.35
```

### Step 3.2 — Jalankan Streamlit (Manual / Testing)

```bash
cd ~/idx-bandarmology
source .venv/bin/activate
streamlit run dashboard/app.py --server.port 8501 --server.address 127.0.0.1
```

Buka di browser (di Android bisa pakai Chrome localhost:8501 kalau port forwarding aktif, atau kita lanjut ke Cloudflare Tunnel).

### Step 3.3 — Auto-start dengan Systemd (Recommended)

Buat service file:

```bash
sudo nano /etc/systemd/system/idx-bandarmology.service
```

Isi (ganti `<USER>` dengan username Debian kamu):
```ini
[Unit]
Description=IDX Bandarmology Streamlit Dashboard
After=network.target postgresql.service

[Service]
Type=simple
User=<USER>
WorkingDirectory=/home/<USER>/idx-bandarmology
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/<USER>/idx-bandarmology/.venv/bin/streamlit run dashboard/app.py --server.port 8501 --server.address 127.0.0.1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Aktifkan:
```bash
sudo systemctl daemon-reload
sudo systemctl enable idx-bandarmology
sudo systemctl start idx-bandarmology
sudo systemctl status idx-bandarmology
```

Kalau `systemctl` tidak tersedia di proot, gunakan `screen` atau `tmux`:
```bash
sudo apt install -y screen
screen -S idx -dm bash -c 'cd ~/idx-bandarmology && source .venv/bin/activate && streamlit run dashboard/app.py --server.port 8501 --server.address 127.0.0.1'
```

---

## 4. Step-by-Step: Cloudflare Tunnel (Akses Publik)

### Step 4.1 — Install `cloudflared`

```bash
# Download binary cloudflared (ARM64 untuk Android/ARM, AMD64 untuk x86)
# Cek arsitektur: uname -m

# Untuk ARM64 (kebanyakan Android modern):
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb

# Untuk AMD64 (jika Droidspaces di emulator/x86):
# curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb

sudo dpkg -i cloudflared.deb
```

### Step 4.2 — Login ke Cloudflare

```bash
cloudflared tunnel login
```

Ini akan print URL. Buka di browser (di HP Android atau PC), login ke Cloudflare, pilih domain kamu. Nanti akan download cert ke `~/.cloudflared/cert.pem`.

### Step 4.3 — Buat Tunnel

```bash
cloudflared tunnel create idx-bandarmology
```

Output akan menunjukkan **Tunnel ID** (contoh: `f47ac10b-58cc-4372-a567-0e02b2c3d479`).

Catat Tunnel ID tersebut.

### Step 4.4 — Buat DNS Route

```bash
cloudflared tunnel route dns idx-bandarmology idx.yourdomain.com
```

Ganti `yourdomain.com` dengan domain kamu. Subdomain `idx` bisa diganti sesuai selera.

### Step 4.5 — Konfigurasi Tunnel

```bash
nano ~/.cloudflared/config.yml
```

Isi:
```yaml
tunnel: <TUNNEL_ID>
credentials-file: /home/<USER>/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: idx.yourdomain.com
    service: http://localhost:8501
    originRequest:
      noTLSVerify: true
  - service: http_status:404
```

Ganti `<TUNNEL_ID>` dan `<USER>`.

### Step 4.6 — Jalankan Tunnel

Manual (testing):
```bash
cloudflared tunnel run idx-bandarmology
```

Kalau sukses, buka `https://idx.yourdomain.com` dari HP lain atau PC.

### Step 4.7 — Auto-start Cloudflare Tunnel (Systemd)

```bash
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared
```

Atau kalau systemd tidak tersedia, pakai `screen`:
```bash
screen -S cf -dm cloudflared tunnel run idx-bandarmology
```

---

## 5. Ringkasan Port & Service

| Service | Port | Akses |
|---------|------|-------|
| PostgreSQL | 5432 | Local only (127.0.0.1) |
| Streamlit | 8501 | Local + via Cloudflare Tunnel |
| Cloudflare Tunnel | — | Publik di `https://idx.yourdomain.com` |

---

## 6. Troubleshooting Droidspaces

### PostgreSQL tidak start
```bash
# Cek log
sudo cat /var/log/postgresql/postgresql-15-main.log

# Fix permission data directory (common di proot)
sudo chown -R postgres:postgres /var/lib/postgresql
sudo chmod 700 /var/lib/postgresql/15/main
```

### `psycopg2` gagal install
```bash
sudo apt install -y libpq-dev python3-dev
pip install psycopg2-binary --force-reinstall
```

### Streamlit tidak bisa diakses publik
Pastikan `--server.address 127.0.0.1` (bukan `0.0.0.0`). Cloudflare Tunnel akan forward dari publik ke localhost.

### Cloudflare Tunnel disconnect
```bash
# Cek status
cloudflared tunnel info idx-bandarmology

# Restart
cloudflared tunnel run idx-bandarmology
```

---

## 7. Keamanan

1. **Jangan expose PostgreSQL ke publik** — pastikan `postgresql.conf` punya:
   ```
   listen_addresses = 'localhost'
   ```

2. **Gunakan firewall** (jika tersedia di Droidspaces):
   ```bash
   sudo apt install ufw
   sudo ufw default deny incoming
   sudo ufw allow ssh  # jika perlu SSH
   sudo ufw enable
   ```

3. **Cloudflare Tunnel aman** — tidak perlu buka port di router/Android; traffic di-encrypt end-to-end.

4. **`.env` jangan di-commit** — sudah ada di `.gitignore`, tetap pastikan:
   ```bash
   git update-index --skip-worktree .env
   ```

---

## 8. File yang Sudah Disediakan

| File | Lokasi Output |
|------|---------------|
| `config.py` (PostgreSQL) | `sandbox:///mnt/agents/output/idx_bandarmology_postgres/config.py` |
| `storage.py` (PostgreSQL) | `sandbox:///mnt/agents/output/idx_bandarmology_postgres/storage.py` |
| `.env.example` | `sandbox:///mnt/agents/output/idx_bandarmology_postgres/.env.example` |
| `requirements_additions.txt` | `sandbox:///mnt/agents/output/idx_bandarmology_postgres/requirements_additions.txt` |
| `cloudflared_config.yml` | `sandbox:///mnt/agents/output/idx_bandarmology_postgres/cloudflared_config.yml` |
| `streamlit.service` | `sandbox:///mnt/agents/output/idx_bandarmology_postgres/streamlit.service` |

### Cara Pakai
1. Download `config.py` dan `storage.py`, timpa file lama di `src/idx_bandarmology/`
2. Tambahkan `psycopg2-binary>=2.9` ke `requirements.txt`
3. Download `.env.example`, rename jadi `.env`, isi token & DB URL
4. Ikuti step-by-step di atas
