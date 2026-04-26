# Developer Guide - PIKAS Architecture

Dokumen ini menjelaskan detail teknis arsitektur PIKAS untuk pengembang yang ingin berkontribusi atau melakukan maintenance.

## 1. Arsitektur Data

### is_dirty Protocol
Sistem menggunakan field `is_dirty` pada model `FRAEntry` untuk melindungi data input operator.
- **`is_dirty = True`**: Menandakan operator telah mengubah data di aplikasi. Saat melakukan **PULL** dari Google Sheets, field bertipe `TWO_WAY` (seperti Kendala, Solusi) **TIDAK AKAN** ditimpa oleh data dari Sheets.
- **`is_dirty = False`**: Data di database sinkron dengan Sheets. Field `PULL_ONLY` (seperti Target, Capaian dari rumus GSheet) akan selalu ditimpa tanpa mempedulikan status `is_dirty`.

### JSON Mapping Protocol
Setiap IKU memiliki konfigurasi pemetaan sel GSheet yang disimpan dalam format JSON di `MasterIKU.config_mapping`.
Contoh struktur:
```json
{
  "proxy_config": {
    "has_proxy": true,
    "x_label": "Jumlah Sampel",
    "y_label": "Total Populasi"
  },
  "gsheet_mapping": {
    "sheet_name": "LK_Induk",
    "cells": {
      "target_gsheet": {"coord": "M15", "mode": "PULL_ONLY"},
      "realisasi_iku": {"coord": "AA15", "mode": "TWO_WAY"}
    }
  }
}
```

## 2. Struktur Direktori

- `/pikas_app/models.py`: Definisi schema database (MasterIKU, FRAEntry, AppConfig).
- `/pikas_app/services/`: Logika bisnis berat (GSheet sync, GDrive explorer).
- `/pikas_app/templates/`: UI menggunakan Tailwind CSS dan Alpine.js untuk reaktivitas.
- `/pikas_project/`: Konfigurasi inti Django.

## 3. Integrasi Eksternal

### Google Sheets Engine
Menggunakan library `gspread`. Proses sinkronisasi dilakukan secara **Batch** (mengambil banyak sel dalam satu kali request) untuk menghindari limitasi kuota API Google.

### Google Drive Explorer
Mengekstrak Folder ID dari link Drive yang diinput Admin, lalu melakukan listing file menggunakan Service Account. Hasilnya di-cache selama 300 detik untuk performa maksimal.

## 4. Alur Kerja Git

1. Gunakan branch `feature/nama-fitur` untuk pengembangan baru.
2. Pastikan `requirements.txt` diperbarui jika menambah library baru.
3. Selalu jalankan `python manage.py check` sebelum melakukan commit.

## 5. Keamanan

- **DILARANG** melakukan commit pada file `service_account.json` atau `.env`.
- Rahasia API harus dikelola melalui variabel lingkungan atau file yang di-ignore.
