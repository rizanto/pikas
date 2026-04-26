# PIKAS (Performance Indicators Knowledgebase Accountability System)

PIKAS adalah portal monitoring Indikator Kinerja Utama (IKU) dan Anggaran Sektoral yang dirancang untuk Badan Pusat Statistik (BPS). Sistem ini mengintegrasikan data dari Google Sheets secara real-time ke dalam dashboard monitoring yang modern dan interaktif.

## 🚀 Fitur Utama

- **Dashboard Real-time**: Visualisasi progres pengisian IKU, capaian kinerja, dan status tim kerja dalam format "Matrix Monitor" yang padat informasi.
- **Workspace Operator**: Halaman kerja khusus bagi operator untuk mengisi realisasi, kendala, solusi, dan rencana tindak lanjut (RTL) dengan validasi ketat.
- **Integrasi Google Drive**: Explorer file terintegrasi untuk melihat bukti kinerja langsung dari folder Google Drive tanpa meninggalkan aplikasi.
- **Sinkronisasi Google Sheets**: Engine PULL/PUSH yang efisien menggunakan Service Account untuk menjaga konsistensi data antara aplikasi dan spreadsheet induk.
- **Sistem Review**: Alur kerja peninjauan bagi supervisor untuk memvalidasi isian dan bukti kinerja yang diunggah oleh tim.
- **Periode & Penguncian**: Manajemen triwulanan (TW I - TW IV) dengan fitur penguncian periode untuk mencegah perubahan data setelah batas waktu.

## 🛠️ Tech Stack

- **Backend**: Django (Python)
- **Database**: PostgreSQL (Production) / SQLite (Development)
- **Frontend**: Vanilla JS, Alpine.js, Tailwind CSS
- **Integrasi**: Google Sheets API, Google Drive API (via Service Account)

## 📋 Prasyarat

- Python 3.10+
- Service Account Google Cloud (dengan akses Google Sheets & Drive API)
- File `service_account.json` diletakkan di direktori root.

## 🔧 Instalasi

1. **Clone Repository**
   ```bash
   git clone https://github.com/username/pikas.git
   cd pikas
   ```

2. **Setup Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. **Install Dependensi**
   ```bash
   pip install -r requirements.txt
   ```

4. **Konfigurasi Database**
   Lakukan migrasi database:
   ```bash
   python manage.py migrate
   ```

5. **Buat Superuser**
   ```bash
   python manage.py createsuperuser
   ```

6. **Jalankan Server**
   ```bash
   python manage.py runserver
   ```

## 📄 Lisensi

Proyek ini dikembangkan untuk penggunaan internal Badan Pusat Statistik.

---
*Developed with ❤️ for BPS Indonesia*
