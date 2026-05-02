# Panduan Teknis PIKAS

> **Copyright (c) 2026 Ilham Rizanto. Seluruh hak cipta dilindungi.**

Dokumen ini menjelaskan arsitektur teknis, alur data, dan cara kerja komponen-komponen utama dalam sistem PIKAS.

---

## Daftar Isi

1. [Arsitektur Sistem](#1-arsitektur-sistem)
2. [Model Database](#2-model-database)
3. [Alur Sinkronisasi Google Sheets](#3-alur-sinkronisasi-google-sheets)
4. [Sistem Full-Sync RCO](#4-sistem-full-sync-rco)
5. [Sistem Kontrol Akses](#5-sistem-kontrol-akses)
6. [API Endpoint Internal](#6-api-endpoint-internal)

---

## 1. Arsitektur Sistem

PIKAS menggunakan arsitektur monolitik berbasis Django dengan integrasi ke Google Workspace melalui Service Account.

```
┌─────────────────────────────────────────────────────┐
│                   PENGGUNA (Browser)                │
│         Admin │ Operator │ Viewer                   │
└───────────────────────┬─────────────────────────────┘
                        │ HTTPS
                        ▼
┌─────────────────────────────────────────────────────┐
│              Django Application Server              │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │   Views /   │  │   Models &   │  │  Services │  │
│  │  Templates  │  │  Migrations  │  │  (GSheet) │  │
│  └─────────────┘  └──────┬───────┘  └─────┬─────┘  │
└─────────────────────────-┼────────────────┼─────────┘
                           │                │
               ┌───────────┘                │ Service Account
               ▼                            ▼
┌──────────────────────┐      ┌─────────────────────────┐
│  Database            │      │  Google Workspace        │
│  (PostgreSQL/SQLite) │      │  ├── Google Sheets API   │
│                      │      │  └── Google Drive API    │
└──────────────────────┘      └─────────────────────────┘
```

### Komponen Utama

| Komponen | File | Fungsi |
|---|---|---|
| **Routing** | `pikas_app/urls.py` | Mendefinisikan seluruh URL dan memetakannya ke view |
| **Views** | `pikas_app/views.py` | Logika bisnis, render template, dan handler API |
| **Models** | `pikas_app/models.py` | Definisi skema database dan validasi data |
| **GSheet Service** | `pikas_app/services/gsheet_service.py` | Seluruh logika komunikasi dengan Google Sheets |
| **Context Processors** | `pikas_app/context_processors.py` | Data global yang disuntikkan ke setiap template |
| **Decorators** | `pikas_app/decorators.py` | Dekorator kontrol akses berbasis role |

---

## 2. Model Database

PIKAS menggunakan dua domain data yang terpisah namun saling terkait:

### Domain Kertas Kerja (IKU Monitoring)

```
PeriodeKertasKerja          MasterIKU                   FRAEntry
─────────────────           ─────────────────           ─────────────────
id (UUID PK)                id (UUID PK)                id (UUID PK)
tahun                       periode (FK)        ┌──────  iku (OneToOne FK)
triwulan                    kode_indikator      │        kendala
sheet_name                  indikator           │        solusi
config_json  ◄── sumber     tujuan              │        rtl
is_locked        mapping    kode_tujuan         │        pic_rtl
is_configured               sasaran             │        realisasi
                            kode_sasaran        │        is_done
                            has_proxy           │        is_dirty
                            cells (JSON)        │        pic_tim_kerja (FK)
                                                │        pulled_data (JSON)
                                                │
                            ◄───────────────────┘
```

### Domain RCO (Realisasi Capaian Output)

```
TahunKerja          MasterRO                    RealisasiRO
────────────        ─────────────────           ─────────────────
id (UUID PK)        id (UUID PK)                id (UUID PK)
tahun (unique)      tahun (FK)          ┌──────  master_ro (FK)
is_active           kode_iku            │        bulan (1-12)
                    kode_ro             │        konten (TextField)
                    nama_ro             │        last_updated_by (FK)
                    daftar_kegiatan     │        updated_at
                                        │
                    ◄───────────────────┘
```

### Catatan Penting
- `config_json` pada `PeriodeKertasKerja` adalah sumber kebenaran (*source of truth*) untuk seluruh mapping IKU ke koordinat cell GSheet.
- `cells` pada `MasterIKU` adalah salinan mapping yang disalin dari `config_json` saat `MasterIKU` dibuat, sehingga akses lebih cepat tanpa perlu parsing JSON setiap saat.
- `pulled_data` pada `FRAEntry` menyimpan semua nilai yang ditarik dari GSheet (target, capaian, alokasi, PKO, dll.) dalam satu field JSON agar struktur tabel tetap fleksibel.
- `is_dirty` pada `FRAEntry` bertindak sebagai pengaman: jika `True`, proses PULL dari GSheet tidak akan menimpa data yang sudah diisi operator.

---

## 3. Alur Sinkronisasi Google Sheets

Seluruh logika sinkronisasi berada di `pikas_app/services/gsheet_service.py`.

### 3.1 PULL (GSheet → Database)

Proses menarik data dari Google Sheets ke database PIKAS.

```
Admin klik "Pull Data"
        │
        ▼
gsheet_service.pull_periode_data(periode)
        │
        ├─► Autentikasi via Service Account
        │
        ├─► Ambil daftar semua kode IKU dari MasterIKU
        │
        ├─► Kumpulkan SEMUA koordinat cell ke satu list (ranges_to_fetch)
        │
        ├─► Chunking: Bagi list menjadi kelompok 100 range per request
        │   (Mencegah error 400 "URL too long" pada Google Sheets API)
        │
        ├─► Eksekusi batch_get untuk setiap chunk
        │
        ├─► Petakan nilai kembali ke masing-masing IKU
        │
        └─► Update FRAEntry jika is_dirty == False
```

### 3.2 PUSH (Database → GSheet)

Proses mengirim data yang diisi Operator kembali ke Google Sheets.

```
Admin klik "Push Data"
        │
        ▼
gsheet_service.push_periode_data(periode)
        │
        ├─► Kumpulkan semua FRAEntry yang memiliki data TWO_WAY
        │   (kendala, solusi, rtl, realisasi, dll.)
        │
        ├─► Bangun list batch_update sesuai koordinat cell
        │
        └─► Eksekusi values_batch_update ke Google Sheets
```

### 3.3 Mekanisme Chunking Request

Google Sheets API memiliki batas panjang URL. Jika jumlah IKU sangat banyak, seluruh koordinat cell tidak bisa dikirim dalam satu request. PIKAS mengatasi ini dengan membagi request menjadi kelompok 100 range:

```python
CHUNK_SIZE = 100
for i in range(0, len(ranges_to_fetch), CHUNK_SIZE):
    chunk = ranges_to_fetch[i:i + CHUNK_SIZE]
    values_response = spreadsheet.values_batch_get(chunk, ...)
```

---

## 4. Sistem Full-Sync RCO

Berbeda dari Domain IKU yang menggunakan PULL/PUSH, Domain RCO menggunakan mekanisme **Full-State Synchronization**.

### Prinsip Kerja

JSON yang dimasukkan melalui Monaco Editor diperlakukan sebagai **Sumber Kebenaran Mutlak**. Saat tombol "Sync" ditekan, sistem akan:

1. **Baca** seluruh record `MasterRO` yang ada di database untuk `TahunKerja` tersebut.
2. **Bandingkan** dengan data JSON yang dikirim.
3. **Tambahkan** RO yang ada di JSON tapi belum ada di database.
4. **Perbarui** RO yang ada di kedua sisi jika ada perbedaan data.
5. **Hapus** RO yang ada di database tapi sudah tidak ada di JSON.

```
JSON Editor (Source of Truth)
        │
        │  POST /api/bulk-ro/
        ▼
api_bulk_ro()
        │
        ├─► Strip whitespace pada semua kode_ro (sanitasi)
        │
        ├─► Buat set: incoming_codes (dari JSON)
        │
        ├─► Buat set: existing_codes (dari DB)
        │
        ├─► to_delete = existing_codes - incoming_codes ──► DELETE
        │
        ├─► Untuk setiap item di JSON:
        │     ├─► Jika belum ada → CREATE
        │     └─► Jika sudah ada → UPDATE (jika ada perubahan)
        │
        └─► Return: { added, updated, deleted }
```

---

## 5. Sistem Kontrol Akses

PIKAS mengimplementasikan kontrol akses berbasis peran (Role-Based Access Control / RBAC) menggunakan dekorator kustom.

### Hierarki Peran

| Peran | Akses |
|---|---|
| **ADMIN** | Akses penuh: konfigurasi sistem, manajemen pengguna, manajemen RO, kertas kerja |
| **OPERATOR** | Akses terbatas: pengisian workspace IKU dan pencatatan RCO bulanan |
| **VIEWER** | Akses baca-saja: dashboard dan laporan |

### Implementasi Dekorator

```python
# pikas_app/decorators.py
@role_required(['ADMIN'])
def manage_ro_view(request):
    ...

@role_required(['ADMIN', 'OPERATOR'])
def capaian_output_view(request):
    ...
```

---

## 6. API Endpoint Internal

PIKAS mengekspos endpoint internal (JSON) untuk komunikasi antara frontend dan backend tanpa reload halaman.

| Endpoint | Method | Autentikasi | Fungsi |
|---|---|---|---|
| `/api/kertas-kerja/` | GET, POST | Session (Admin) | Manajemen periode kertas kerja |
| `/api/kertas-kerja/<id>/` | GET, POST | Session (Admin) | Konfigurasi mapping per periode |
| `/api/entry/<iku_id>/` | POST | Session (Operator) | Simpan isian operator |
| `/api/bulk-ro/` | POST | Session (Admin) | Full-Sync Master RO dari JSON |
| `/api/rincian-output/` | POST | Session (Admin) | Manajemen individual Master RO |
| `/api/capaian-output/` | POST | Session (Operator/Admin) | Simpan realisasi RCO bulanan |
| `/api/drive-explorer/` | GET | Session | Jelajah file Google Drive |
| `/api/audit-konsistensi/` | GET | Session (Admin) | Audit konsistensi data IKU |

> **Catatan Keamanan**: Seluruh endpoint di atas hanya dapat diakses oleh pengguna yang telah terautentikasi melalui sesi Django (`@login_required`). Tidak ada endpoint yang terbuka untuk publik.

---

*Dokumen ini adalah bagian dari dokumentasi resmi PIKAS.*
*Copyright (c) 2026 Ilham Rizanto. Seluruh hak cipta dilindungi.*
