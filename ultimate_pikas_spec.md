# SYSTEM REQUIREMENT & ARCHITECTURE SPECIFICATION (SRAS)
# PROJECT: PIKAS (Performance Indicators Knowledgebase Accountability System)
# VERSION: 3.0 (EXTREME DENSITY - PRODUCTION READY)
# TARGET: GEMINI 3.1 PRO (HIGH) / SENIOR SYSTEM ARCHITECT
# DIRECTIVE: ZERO HALLUCINATION. STRICT ADHERENCE TO CONTRACTS.

================================================================================
TABLE OF CONTENTS
1. ARCHITECTURAL PARADIGM & CONSTRAINTS
2. DATA LAYER CONTRACTS (ORM & DATABASE SCHEMA)
3. THE JSON MAPPING PROTOCOL (SCHEMA & VALIDATION)
4. INTEGRATION ENGINE (SERVICE LAYER PROTOCOLS)
5. STATE MACHINE & CONCURRENCY (THE is_dirty PROTOCOL)
6. CONTROLLER LAYER (VIEWS & API BOUNDARIES)
7. FRONTEND ARCHITECTURE (DOM, STATE, & STYLING)
8. PHASE-BY-PHASE EXECUTION DIRECTIVE
================================================================================

## 1. ARCHITECTURAL PARADIGM & CONSTRAINTS
AI Agent wajib mematuhi arsitektur ini tanpa kompromi. Dilarang menawarkan *stack* alternatif.

* **Pattern:** Monolith MVT (Model-View-Template) dengan pola *Service Layer*. DILARANG menaruh logika bisnis (API Calls, Data Processing) di dalam `views.py`. Semua logika bisnis HARUS diisolasi di `services/`.
* **Database:** PostgreSQL 15+. DILARANG menggunakan SQLite di *environment* apa pun.
* **State Management:** Server-side state di Postgres. Client-side state murni dikendalikan oleh Alpine.js (`x-data`).
* **Styling:** Utility-first menggunakan Tailwind CSS. Dilarang menulis file `.css` terpisah kecuali untuk `@tailwind` directives.
* **API Protocol:** Semua interaksi ke Google (Drive, Sheets) bersifat *Server-to-Server* menggunakan Service Account (`credentials.json`). Dilarang memaparkan API Key di Frontend.
* **Concurrency Constraint:** Sinkronisasi GSheet menggunakan paradigma *Batching*. Dilarang menggunakan *looping* untuk hit API satu per satu.

---

## 2. DATA LAYER CONTRACTS (ORM & DATABASE SCHEMA)
Definisi model ini adalah "Hukum Besi". AI Agent wajib menulis *Type Hinting*, *Docstrings*, dan *Meta classes* yang tepat. Semua *Primary Key* WAJIB menggunakan `uuid.uuid4`.

### 2.1 `AppConfig` (Singleton Configuration)
Mengontrol "detak jantung" periode pelaporan.
```python
class AppConfig(models.Model):
    """
    Singleton Table. Hanya boleh ada 1 baris (id) di database.
    Mengontrol periode aktif untuk seluruh sistem PIKAS.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    active_year = models.IntegerField(validators=[MinValueValidator(2020)])
    active_quarter = models.IntegerField(choices=[(1, 'TW I'), (2, 'TW II'), (3, 'TW III'), (4, 'TW IV')])
    is_locked = models.BooleanField(default=False, help_text="Jika True, Operator tidak bisa submit/edit FRA.")
    gsheet_id = models.CharField(max_length=255, help_text="ID unik dari URL Google Sheet target.")
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Enforce Singleton Pattern."""
        if AppConfig.objects.exists() and not self.pk:
            raise ValidationError("Hanya boleh ada satu konfigurasi aktif.")
```

### 2.2 `MasterIKU` (Indicator Blueprint & Brain)
Menyimpan definisi IKU dan logika *mapping* sel yang sangat kompleks.
```python
class MasterIKU(models.Model):
    """
    Blueprint untuk setiap IKU/Proksi. 
    Menyimpan JSON config yang memetakan field ke koordinat Google Sheet.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kode_iku = models.CharField(max_length=50, unique=True, db_index=True)
    nama_iku = models.TextField()
    jenis_iku = models.CharField(max_length=20, choices=[('IKU', 'IKU Utama'), ('PROKSI', 'Proksi')])
    jenis_periode = models.CharField(max_length=20, choices=[('TAHUNAN', 'Tahunan'), ('TRIWULANAN', 'Triwulanan')])
    satuan = models.CharField(max_length=50)
    target_setahun = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    
    # KUNCI UTAMA SISTEM: JSON MAPPING
    config_mapping = models.JSONField(validators=[validate_pikas_json_schema])
    
    # URL Drive Default
    link_gdrive_kinerja = models.URLField(max_length=500, null=True, blank=True)
    link_gdrive_solusi = models.URLField(max_length=500, null=True, blank=True)
    link_gdrive_tindak_lanjut = models.URLField(max_length=500, null=True, blank=True)
    
    class Meta:
        verbose_name_plural = "Master IKU"
        ordering = ['kode_iku']
```

### 2.3 `FRAEntry` (Transactional Ledger)
Tabel transaksi yang merekam input operator dan hasil PULL dari GSheet.
```python
class FRAEntry(models.Model):
    """
    Data pergerakan triwulanan. Satu IKU memiliki 4 FRAEntry dalam 1 tahun.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    iku = models.ForeignKey(MasterIKU, related_name='entries', on_delete=models.CASCADE)
    tahun = models.IntegerField(db_index=True)
    triwulan = models.IntegerField(choices=[(1, 'TW I'), (2, 'TW II'), (3, 'TW III'), (4, 'TW IV')])
    
    # Quantitative Fields (Input Operator / PUSH)
    realisasi_kumulatif_iku = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    proxy_x = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    proxy_y = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    
    # Result Fields (PULL ONLY - Read Only for Operator)
    capaian_kinerja_gsheet = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    target_gsheet = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    
    # Qualitative / Narrative Fields (Input Operator / TWO_WAY)
    kendala = models.TextField(blank=True, null=True)
    solusi = models.TextField(blank=True, null=True)
    rtl = models.TextField(blank=True, null=True)
    pic = models.CharField(max_length=255, blank=True, null=True)
    batas_waktu = models.CharField(max_length=255, blank=True, null=True)
    
    # State & Audit Flags
    is_done = models.BooleanField(default=False)
    is_dirty = models.BooleanField(default=False, help_text="TRUE jika sudah di-save operator. Memblokir PULL overwrite.")
    last_synced_at = models.DateTimeField(null=True, blank=True)
    pic_tim_kerja = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = ('iku', 'tahun', 'triwulan')
```

---

## 3. THE JSON MAPPING PROTOCOL (SCHEMA & VALIDATION)

Agent AI wajib mengimplementasikan fungsi `validate_pikas_json_schema(value: dict)` yang dipanggil oleh field `MasterIKU.config_mapping`.

### 3.1 Strict Schema Definition
```json
{
  "proxy_config": {
    "has_proxy": "boolean (REQUIRED)",
    "x_label": "string (REQUIRED IF has_proxy is true)",
    "y_label": "string (REQUIRED IF has_proxy is true)"
  },
  "gsheet_mapping": {
    "sheet_name": "string (REQUIRED. e.g., 'LK_Kabkot')",
    "cells": {
      "target_gsheet": {"coord": "string (e.g., 'M15')", "mode": "PULL_ONLY"},
      "capaian_kinerja": {"coord": "string", "mode": "PULL_ONLY"},
      "realisasi_iku": {"coord": "string", "mode": "TWO_WAY"},
      "proxy_x": {"coord": "string", "mode": "TWO_WAY"},
      "proxy_y": {"coord": "string", "mode": "TWO_WAY"},
      "kendala": {"coord": "string", "mode": "TWO_WAY"},
      "solusi": {"coord": "string", "mode": "TWO_WAY"},
      "rtl": {"coord": "string", "mode": "TWO_WAY"},
      "pic": {"coord": "string", "mode": "TWO_WAY"},
      "batas_waktu": {"coord": "string", "mode": "TWO_WAY"}
    }
  }
}
```

### 3.2 Validation Rules (Python Logic)
Fungsi validasi tidak boleh hanya mengecek tipe data, tapi harus memverifikasi integritas logis:
1. Jika `has_proxy` True, node `cells` WAJIB memiliki sub-node `proxy_x` dan `proxy_y` beserta koordinatnya.
2. Jika `has_proxy` False, node `cells` DILARANG memiliki sub-node `proxy_x` dan `proxy_y`.
3. Regex check untuk `coord`: Harus berformat Letter-Number (e.g., `^[A-Z]{1,3}[0-9]+$`).
4. `mode` HANYA boleh bernilai `PULL_ONLY` atau `TWO_WAY`.

---

## 4. INTEGRATION ENGINE (SERVICE LAYER PROTOCOLS)

### 4.1 `services/gsheet_service.py`
Ini adalah core engine. Agent AI WAJIB menggunakan `batch_get` dan `batch_update` dari library `gspread`.

**A. The PULL Function (`pull_active_period_data()`)**
* **Payload Builder:** Iterasi semua `MasterIKU`. Kumpulkan list `coord` dari JSON. Format request ranges: `['LK_Kabkot!M15', 'LK_Kabkot!P15', ...]`.
* **API Call:** Eksekusi `worksheet.batch_get(ranges)`.
* **Data Parsing:** Petakan kembali array hasil dari Google ke masing-masing objek `FRAEntry`.
* **State Enforcement (CRITICAL):** Lakukan pengecekan `is_dirty`. (Lihat Bab 5).
* **Database Write:** Gunakan `FRAEntry.objects.bulk_update()` untuk meminimalisir hit ke Postgres.

**B. The PUSH Function (`push_active_period_data()`)**
* **Payload Builder:** Ambil semua `FRAEntry` pada periode aktif. Baca konfigurasi JSON masing-masing `MasterIKU`.
* **Matrix Construction:** Buat list dictionary data. `[{'range': 'LK_Kabkot!AA15', 'values': [[entry.kendala]]}, ...]`.
* **Sanitization:** Text dari DB harus dimanipulasi: ganti CRLF dengan `\n` agar GSheet merendernya sebagai line-break dalam satu sel.
* **API Call:** Eksekusi `worksheet.batch_update(payload)`.

### 4.2 `services/gdrive_service.py`
* **Folder Extraction:** Ekstrak ID dari format `https://drive.google.com/drive/folders/{ID}?usp=sharing` menggunakan regex `r'folders/([a-zA-Z0-9_-]+)'`.
* **API Call:** Gunakan `google-api-python-client`. Method: `service.files().list()`.
* **Query Param:** `q="'{folder_id}' in parents and trashed=false"`.
* **Response Formatting:** Kembalikan JSON terstruktur: `[{"id": "...", "name": "...", "mimeType": "...", "size": "...", "lastModified": "..."}]`.
* **Caching Strategy:** Bungkus fungsi ini dengan `django.core.cache`. Timeout set di 300 detik. Key `drive_list_{folder_id}`.

---

## 5. STATE MACHINE & CONCURRENCY (THE is_dirty PROTOCOL)

Ini adalah protokol mutlak untuk melindungi data operator dari penimpaan massal (overwrite) oleh Admin. Agent AI wajib menerjemahkan tabel kebenaran (*truth table*) ini ke dalam logika backend.

### 5.1 The Overwrite Matrix (During PULL Operation)

| Field Mode (JSON) | `FRAEntry.is_dirty` | Action Required by Backend |
| :--- | :--- | :--- |
| `PULL_ONLY` (Target, Capaian) | `False` | **OVERWRITE** DB dengan data GSheet |
| `PULL_ONLY` (Target, Capaian) | `True` | **OVERWRITE** DB dengan data GSheet |
| `TWO_WAY` (Kendala, Solusi, RTL) | `False` | **OVERWRITE** DB dengan data GSheet |
| `TWO_WAY` (Kendala, Solusi, RTL) | `True` | **SKIP OVERWRITE**. Pertahankan data di Postgres. |

*Justifikasi:* Field `PULL_ONLY` adalah otoritas mutlak GSheet (Admin Induk). Field `TWO_WAY` adalah narasi yang diketik operator. Jika `is_dirty` = True, berarti operator sedang/telah mengerjakan FRA tersebut. Menarik data kosong/lama dari GSheet akan merusak pekerjaan mereka.

### 5.2 Triggering `is_dirty`
* Setiap kali HTTP POST/PATCH diterima di `views.py` dari form operator, backend WAJIB mengeset `entry.is_dirty = True`.
* Admin memiliki hak istimewa (Super Button) untuk me-reset `is_dirty` menjadi `False` jika dibutuhkan (Force PULL).

---

## 6. CONTROLLER LAYER (VIEWS & API BOUNDARIES)

Dilarang merender form HTML dari server untuk input (jangan pakai `forms.ModelForm` tradisional). Gunakan pendekatan *Headless-lite*: View Django mengembalikan HTML Shell (dengan Tailwind), lalu mengambil data via API internal (JsonResponse) untuk dirender oleh Alpine.js.

### 6.1 View: `dashboard_view` (The Matrix Monitor)
* **Query:** Ambil semua `FRAEntry` untuk `AppConfig.active_quarter` dan `active_year`.
* **Context:** `{'entries': entries, 'config': current_config}`.
* **UI Logic:** Tabel horizontal IKU. Gunakan logic warna untuk kotak status `[K][S][R][P][B][L][L][L]`.

### 6.2 View: `operator_workspace_view`
* **Query:** Filter `FRAEntry` berdasarkan `pic_tim_kerja = request.user` dan periode aktif.
* **Context Enrichment (T-1 RTL Injector):**
    Untuk setiap `FRAEntry` Triwulan `N`, lakukan query ke `FRAEntry` Triwulan `N-1` pada `iku_id` yang sama. Ambil field `rtl`. Masukkan nilai ini ke dalam context dictionary untuk dirender sebagai "Referensi Tindak Lanjut Triwulan Sebelumnya".

### 6.3 Internal API: `/api/gdrive-explorer/<folder_id>/`
* Method: GET.
* Middleware: Memerlukan otentikasi session.
* Response: Murni JSON array of files. Di-consume oleh Alpine.js di modal.

---

## 7. FRONTEND ARCHITECTURE (DOM, STATE, & STYLING)

Tampilan bukan opsional. Agent AI WAJIB menghasilkan UI yang merepresentasikan SaaS B2B "High-End".

### 7.1 Tailwind Global Directives
```css
/* Inject via CDN or PostCSS */
@layer base {
  body { @apply bg-slate-900 text-slate-200 font-sans antialiased; }
}
@layer components {
  .pikas-card { @apply bg-slate-800 border border-slate-700 rounded-xl shadow-lg p-6; }
  .pikas-input { @apply bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent p-3 w-full; }
  .pikas-btn-primary { @apply bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-bold py-2 px-4 rounded-lg transition-all duration-300 shadow-md hover:shadow-purple-500/50; }
  .pikas-btn-outline { @apply border border-pink-600 text-pink-500 hover:bg-pink-600/10 font-bold py-2 px-4 rounded-lg transition-all duration-300; }
}
```

### 7.2 Alpine.js Form State (`x-data`)
Form entri IKU harus reaktif. Contoh struktur *x-data* yang wajib diterapkan Agent:
```javascript
function ikuFormState(initialData, proxyConfig) {
  return {
    isSubmitting: false,
    hasProxy: proxyConfig.has_proxy,
    proxyX: initialData.proxy_x,
    proxyY: initialData.proxy_y,
    kendala: initialData.kendala,
    // ...
    async saveEntry(entryId) {
       this.isSubmitting = true;
       // FETCH API POST logic here
       // On success: Dispatch Alpine custom event for Toast notification
       this.isSubmitting = false;
    }
  }
}
```

### 7.3 Modal GDrive Viewer (`<template x-teleport="body">`)
Wajib menggunakan teleport agar tidak terjebak dalam `z-index` stacking context.
* **Struktur UI Kiri (Tree):** List vertikal dengan `overflow-y-auto`. Ikon berbeda untuk `.pdf` dan folder.
* **Struktur UI Kanan (Preview):** `<iframe :src="selectedFileId ? 'https://drive.google.com/file/d/' + selectedFileId + '/preview' : ''" class="w-full h-full rounded-lg border border-slate-700"></iframe>`
* **Empty State:** Tampilkan ilustrasi SVG "Folder Kosong" jika `selectedFileId` null.

---

## 8. PHASE-BY-PHASE EXECUTION DIRECTIVE (UNTUK AI)

Agent AI **TIDAK DIIZINKAN** menulis seluruh kode dalam satu waktu. Jika ini dilanggar, eksekusi dianggap GAGAL.

* **PHASE 1 (CORE INFRASTRUCTURE):** Setup Django settings (Postgres). Tulis `models.py` (Bab 2) beserta fungsi `validate_pikas_json_schema` (Bab 3). Tunggu verifikasi manusia.
* **PHASE 2 (INTEGRATION ENGINE):** Tulis `services/gsheet_service.py` dan `services/gdrive_service.py` (Bab 4). Terapkan protokol `is_dirty` secara akurat. Tunggu verifikasi manusia.
* **PHASE 3 (API & VIEWS):** Tulis `views.py` (Bab 6) dan `urls.py`. Rancang payload JSON untuk API. Tunggu verifikasi manusia.
* **PHASE 4 (UI/UX - THE DASHBOARD):** Rancang Base Template, Navbar, Sidebar, dan Dashboard Matrix menggunakan Tailwind & Alpine. Tunggu verifikasi manusia.
* **PHASE 5 (UI/UX - THE WORKSPACE):** Rancang Form Entri IKU, Dynamic Proxy UI, dan GDrive Viewer Modal. Tunggu verifikasi manusia.

================================================================================
END OF SPECIFICATION
================================================================================