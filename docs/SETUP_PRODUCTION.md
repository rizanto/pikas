# Panduan Setup Produksi PIKAS

> **Copyright (c) 2026 Ilham Rizanto. Seluruh hak cipta dilindungi.**

Dokumen ini adalah panduan lengkap untuk melakukan deployment PIKAS ke lingkungan produksi menggunakan VPS Linux, Gunicorn, Nginx, dan PostgreSQL.

---

## Daftar Isi

1. [Prasyarat](#1-prasyarat)
2. [Konfigurasi Google Cloud (Service Account)](#2-konfigurasi-google-cloud)
3. [Setup Server (VPS Linux)](#3-setup-server)
4. [Konfigurasi Environment Variables](#4-konfigurasi-environment-variables)
5. [Deployment dengan Gunicorn](#5-deployment-dengan-gunicorn)
6. [Konfigurasi Nginx sebagai Reverse Proxy](#6-konfigurasi-nginx)
7. [SSL/HTTPS dengan Let's Encrypt](#7-ssl-https)
8. [Deployment dengan Docker (Alternatif)](#8-deployment-dengan-docker)
9. [Pemeliharaan Rutin](#9-pemeliharaan-rutin)

---

## 1. Prasyarat

Sebelum memulai, pastikan Anda telah memiliki:

- **VPS** dengan OS Ubuntu 22.04 LTS (atau yang setara)
- **Akses SSH** ke server dengan hak akses `sudo`
- **Domain atau subdomain** yang sudah diarahkan ke IP VPS (untuk SSL)
- **Akun Google Cloud** dengan project yang aktif
- **Google Spreadsheet** yang akan menjadi kertas kerja, sudah dibuat dan siap dikonfigurasi

---

## 2. Konfigurasi Google Cloud

Langkah ini dilakukan di [Google Cloud Console](https://console.cloud.google.com/) dan hanya perlu dilakukan satu kali.

### 2.1 Aktifkan API

1. Masuk ke Google Cloud Console.
2. Buka menu **APIs & Services > Library**.
3. Cari dan aktifkan dua API berikut:
   - `Google Sheets API`
   - `Google Drive API`

### 2.2 Buat Service Account

1. Buka menu **IAM & Admin > Service Accounts**.
2. Klik **Create Service Account**.
3. Isi nama (misal: `pikas-service-account`) dan klik **Create and Continue**.
4. Pada tahap "Grant this service account access", pilih role **Editor** (atau buat role kustom yang lebih spesifik).
5. Klik **Done**.

### 2.3 Buat Kunci Service Account (JSON)

1. Klik pada Service Account yang baru dibuat.
2. Buka tab **Keys > Add Key > Create new key**.
3. Pilih format **JSON** dan klik **Create**.
4. File `*.json` akan otomatis terunduh. **Simpan file ini dengan aman, jangan unggah ke repositori!**

### 2.4 Bagikan Spreadsheet ke Service Account

1. Buka file JSON Service Account. Salin nilai dari field `"client_email"`.
   ```
   contoh: pikas-service-account@nama-project.iam.gserviceaccount.com
   ```
2. Buka Google Spreadsheet kertas kerja Anda.
3. Klik tombol **Share (Bagikan)**.
4. Tambahkan email Service Account tersebut dengan izin **Editor**.

---

## 3. Setup Server

Jalankan perintah-perintah berikut di VPS Anda via SSH.

### 3.1 Update Sistem & Install Paket Dasar

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv nginx postgresql postgresql-contrib git -y
```

### 3.2 Konfigurasi PostgreSQL

```bash
# Masuk ke shell PostgreSQL
sudo -u postgres psql

# Di dalam shell PostgreSQL:
CREATE DATABASE pikas_db;
CREATE USER pikas_user WITH PASSWORD 'password_kuat_anda';
ALTER ROLE pikas_user SET client_encoding TO 'utf8';
ALTER ROLE pikas_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE pikas_user SET timezone TO 'Asia/Jakarta';
GRANT ALL PRIVILEGES ON DATABASE pikas_db TO pikas_user;
\q
```

### 3.3 Clone Repositori

```bash
cd /var/www
sudo git clone https://github.com/ilhamrizanto/pikas.git
sudo chown -R $USER:$USER /var/www/pikas
cd /var/www/pikas
```

### 3.4 Setup Virtual Environment & Dependensi

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Konfigurasi Environment Variables

Salin template dan isi dengan nilai produksi yang sebenarnya.

```bash
cp .env.example .env
nano .env
```

**Isi `.env` untuk produksi:**

```env
# === BRANDING ===
SATKER_NAME=Nama Satuan Kerja Anda

# === DJANGO ===
SECRET_KEY=buat-secret-key-yang-sangat-panjang-dan-acak-minimal-50-karakter
DEBUG=False
ALLOWED_HOSTS=domain-anda.com,www.domain-anda.com
CSRF_TRUSTED_ORIGINS=https://domain-anda.com,https://www.domain-anda.com

# === DATABASE ===
DATABASE_URL=postgresql://pikas_user:password_kuat_anda@localhost:5432/pikas_db

# === GOOGLE API ===
# Salin isi file JSON service account ke sini dalam satu baris
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}
```

> **Peringatan**: Jangan pernah menggunakan `DEBUG=True` di lingkungan produksi.

### 4.1 Jalankan Migrasi & Kumpulkan Aset Statis

```bash
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

---

## 5. Deployment dengan Gunicorn

### 5.1 Test Gunicorn

```bash
source venv/bin/activate
gunicorn --bind 0.0.0.0:8000 pikas_project.wsgi:application
```

Jika berjalan tanpa error, hentikan dengan `Ctrl+C` dan lanjut ke langkah berikutnya.

### 5.2 Buat Systemd Service

```bash
sudo nano /etc/systemd/system/pikas.service
```

Isi dengan konfigurasi berikut:

```ini
[Unit]
Description=PIKAS Gunicorn Application Server
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/pikas
EnvironmentFile=/var/www/pikas/.env
ExecStart=/var/www/pikas/venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/run/pikas.sock \
          pikas_project.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

### 5.3 Aktifkan dan Jalankan Service

```bash
sudo systemctl daemon-reload
sudo systemctl start pikas
sudo systemctl enable pikas

# Cek status
sudo systemctl status pikas
```

---

## 6. Konfigurasi Nginx

```bash
sudo nano /etc/nginx/sites-available/pikas
```

Isi dengan konfigurasi berikut:

```nginx
server {
    listen 80;
    server_name domain-anda.com www.domain-anda.com;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        root /var/www/pikas;
    }

    location /media/ {
        root /var/www/pikas;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/pikas.sock;
        proxy_read_timeout 120s;
        proxy_connect_timeout 120s;
    }

    client_max_body_size 10M;
}
```

### Aktifkan Konfigurasi Nginx

```bash
sudo ln -s /etc/nginx/sites-available/pikas /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 7. SSL/HTTPS dengan Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d domain-anda.com -d www.domain-anda.com
```

Ikuti instruksi di layar. Setelah selesai, Certbot akan otomatis memperbarui konfigurasi Nginx untuk HTTPS.

Verifikasi pembaruan sertifikat otomatis berjalan:

```bash
sudo certbot renew --dry-run
```

---

## 8. Deployment dengan Docker (Alternatif)

Jika Anda lebih memilih deployment berbasis container, PIKAS sudah menyertakan `Dockerfile`.

```bash
# Build image
docker build -t pikas:latest .

# Jalankan container
docker run -d \
  --name pikas \
  -p 8000:8000 \
  --env-file .env \
  pikas:latest
```

> **Catatan**: Untuk produksi dengan Docker, disarankan menggunakan Docker Compose dengan layanan terpisah untuk PostgreSQL dan Nginx.

---

## 9. Pemeliharaan Rutin

### Update Aplikasi

```bash
cd /var/www/pikas
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart pikas
```

### Backup Database

```bash
# Backup
sudo -u postgres pg_dump pikas_db > backup_$(date +%Y%m%d).sql

# Restore
sudo -u postgres psql pikas_db < backup_YYYYMMDD.sql
```

### Monitoring Log

```bash
# Log Gunicorn
sudo journalctl -u pikas -f

# Log Nginx
sudo tail -f /var/log/nginx/error.log
```

---

*Dokumen ini adalah bagian dari dokumentasi resmi PIKAS.*
*Copyright (c) 2026 Ilham Rizanto. Seluruh hak cipta dilindungi.*
