# SYSTEM REQUIREMENT & ARCHITECTURE SPECIFICATION (SRAS)
# SYSTEM: PIKAS (Performance Indicators Knowledgebase Accountability System)
# ENVIRONMENT: Production
# TONE_FOR_AGENT: Strict, Type-Safe, Modular, No-Hallucination.

## 1. SYSTEM DEFINITION & BOUNDARIES
PIKAS is a centralized Knowledgebase and Accountability Middleware for BPS SAKIP.
- **Core Loop:** PULL (Init data from GSheet) -> ENTRY (Mutate state in Postgres) -> PUSH (Batch update to GSheet).
- **Source of Truth:** Postgres (during active period) -> GSheet (Final output).
- **Tech Stack:** Django 5.x (Backend), PostgreSQL 15+ (DB), Tailwind CSS + Alpine.js (Frontend UI/Reactivity), Google APIs (Drive, Sheets).
- **Design Pattern:** Monolith MVT with Fat Models and Service Layers for API Integrations.

## 2. DATABASE SCHEMA (STRICT TYPING)
Agent must implement these exact models. Do not invent new fields.

### 2.1 Model: `AppConfig` (Singleton Pattern)
Controls the global state of the application.
- `id`: UUID (Primary Key)
- `active_year`: Integer (e.g., 2026)
- `active_quarter`: Integer (Choices: 1, 2, 3, 4)
- `is_locked`: Boolean (Default: False). If True, blocks all `FRAEntry` mutations.
- `gsheet_id`: String (Google Sheet ID target)

### 2.2 Model: `MasterIKU` (Static & Config Hub)
- `id`: UUID
- `kode_iku`: CharField(max_length=50, unique=True, db_index=True)
- `nama_iku`: TextField
- `jenis_iku`: CharField (Choices: 'IKU', 'Proksi')
- `jenis_periode`: CharField (Choices: 'Tahunan', 'Triwulanan')
- `satuan`: CharField(max_length=50)
- `target_setahun`: DecimalField(max_digits=10, decimal_places=2, null=True)
- `config_mapping`: JSONField (MUST follow Schema defined in Section 3)
- `link_gdrive_kinerja`: URLField(null=True)
- `link_gdrive_solusi`: URLField(null=True)
- `link_gdrive_tindak_lanjut`: URLField(null=True)

### 2.3 Model: `FRAEntry` (Transactional Data)
- `id`: UUID
- `iku`: ForeignKey(MasterIKU, on_delete=CASCADE, related_name='entries')
- `tahun`: IntegerField (Indexed)
- `triwulan`: IntegerField (Choices: 1, 2, 3, 4)
- `realisasi_iku`: DecimalField(max_digits=10, decimal_places=2, null=True)
- `proxy_x`: DecimalField(max_digits=10, decimal_places=2, null=True) # Numerator
- `proxy_y`: DecimalField(max_digits=10, decimal_places=2, null=True) # Denominator
- `capaian_kinerja_gsheet`: DecimalField(max_digits=10, decimal_places=2, null=True) # Pulled, Read-only
- `kendala`: TextField(blank=True)
- `solusi`: TextField(blank=True)
- `rtl`: TextField(blank=True)
- `pic`: CharField(max_length=100, blank=True)
- `batas_waktu`: CharField(max_length=100, blank=True)
- `is_done`: BooleanField(default=False)
- `is_dirty`: BooleanField(default=False) # True if modified by Operator. Blocks PULL overwrite.
- `last_synced_at`: DateTimeField(null=True)
- `created_by`: ForeignKey(User, null=True, on_delete=SET_NULL)

*Constraint:* `unique_together = ('iku', 'tahun', 'triwulan')`

## 3. JSON CONFIGURATION SCHEMA (THE BRAIN)
The `MasterIKU.config_mapping` must strictly validate against this JSON logic. Agent must create a Django validation logic for this JSONField.

```json
{
  "proxy_config": {
    "has_proxy": true,
    "x_label": "Jumlah Publikasi Berkualitas",
    "y_label": "Total Publikasi"
  },
  "gsheet_mapping": {
    "sheet_name": "LK_Kabkot",
    "cells": {
      "target_setahun": {"coord": "M15", "mode": "PULL_ONLY"},
      "realisasi_iku": {"coord": "P15", "mode": "TWO_WAY"},
      "proxy_x": {"coord": "Q15", "mode": "TWO_WAY"},
      "proxy_y": {"coord": "R15", "mode": "TWO_WAY"},
      "capaian_kinerja": {"coord": "S15", "mode": "PULL_ONLY"},
      "kendala": {"coord": "AA15", "mode": "TWO_WAY"},
      "solusi": {"coord": "AB15", "mode": "TWO_WAY"},
      "rtl": {"coord": "AC15", "mode": "TWO_WAY"},
      "pic": {"coord": "AD15", "mode": "TWO_WAY"},
      "batas_waktu": {"coord": "AE15", "mode": "TWO_WAY"}
    }
  }
}
```
*Rule:* - `PULL_ONLY`: Django reads from GSheet, never writes.
- `TWO_WAY`: Django reads for initialization, but Operator can edit, and Admin will PUSH back to GSheet.

## 4. INTEGRATION CONTRACTS (SERVICES LAYER)
Agent MUST NOT put integration logic in Views. Create `services/gsheet_service.py` and `services/gdrive_service.py`.

### 4.1 GSheet Sync Logic
- Use `gspread` library + Google Service Account.
- **PULL Logic:**
  - Read `AppConfig` to get `gsheet_id`.
  - Iterate `MasterIKU`. For each IKU, read `config_mapping`.
  - Fetch values using `batch_get` to avoid rate limits.
  - Write to `FRAEntry`. **CRITICAL:** If `FRAEntry.is_dirty == True`, SKIP overwriting narrative fields (Kendala, Solusi, RTL) to protect Operator's work.
- **PUSH Logic:**
  - Query all `FRAEntry` where `tahun` and `triwulan` match `AppConfig`.
  - Construct a single payload for `batch_update`. DO NOT update cells one by one.
  - Sanitize text: Keep `\n` for line breaks, remove HTML tags.

### 4.2 GDrive Explorer Logic (Read-Only)
- Endpoint: `GET /api/drive-explorer/?url=<gdrive_folder_url>`
- Extract `folder_id` from URL via Regex.
- Use `google-api-python-client`. Call `files.list(q="'<folder_id>' in parents", fields="files(id, name, mimeType, modifiedTime, size)")`.
- **Performance Constraint:** Cache the JSON response in Redis/Django Cache for 5 minutes based on `folder_id` to prevent API quota exhaustion when multiple users open the UI.

## 5. UI/UX & STATE MANAGEMENT (FRONTEND)
Agent must use Tailwind CSS + Alpine.js. No React/Vue.

### 5.1 Design System Variables
- Background: `bg-slate-900`
- Cards: `bg-slate-800 border border-slate-700 rounded-xl shadow-lg`
- Text: `text-slate-200` (Primary), `text-slate-400` (Secondary). Font: Nunito Sans.
- Accents: `bg-gradient-to-r from-purple-600 to-pink-600`.

### 5.2 Page: DASHBOARD (Matrix Progress)
- Fetch active period entries.
- Render table. Indicator Logic:
  ```html
  <div class="flex space-x-1">
    <span :class="entry.kendala ? 'bg-purple-500' : 'border border-slate-600'">K</span>
    <span :class="entry.solusi ? 'bg-purple-500' : 'border border-slate-600'">S</span>
  </div>
  ```

### 5.3 Page: IKU ENTRY (Operator Form)
- **T1-T2 Auto-Populate Logic:** Backend must inject `previous_rtl` text into the template context based on `triwulan - 1` logic.
- **Dynamic Proxy Fields:** Use Alpine.js to conditionally render Proxy X and Y fields based on the injected `config_mapping.proxy_config.has_proxy` boolean.
- Use `@submit.prevent` in Alpine to handle form submission via fetch API, showing a loading spinner to prevent double-click.

### 5.4 GDrive Viewer Modal
- Implement as an Alpine component `<div x-data="{ open: false, selectedFileId: null }">`.
- Left panel: Iterates cached JSON from Drive API.
- Right panel: `<iframe :src="'https://drive.google.com/file/d/' + selectedFileId + '/preview'"></iframe>`.

## 6. EXECUTION DIRECTIVE FOR AI AGENT
Execute this project in strict chronological phases. DO NOT proceed to the next phase until the current phase is fully coded and verified.

- **PHASE 1 (Foundation):** Setup Django, Postgres, implement `models.py` (Section 2) and JSON validation.
- **PHASE 2 (The Brain):** Build `gsheet_service.py` and `gdrive_service.py` (Section 4). Ensure batch processing is used.
- **PHASE 3 (API & Views):** Create Django views/endpoints to connect the models and services.
- **PHASE 4 (UI Construction):** Build templates using Tailwind and Alpine (Section 5), starting from layout, Dashboard, IKU Entry, to the Drive Modal.
- **PHASE 5 (Admin Control):** Build the Kertas Kerja configuration panel for the Admin to set JSON mappings and trigger PULL/PUSH.
```