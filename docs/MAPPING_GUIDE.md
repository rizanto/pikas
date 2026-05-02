# Panduan Mapping PIKAS

> **Copyright (c) 2026 Ilham Rizanto. Seluruh hak cipta dilindungi.**

Dokumen ini adalah panduan lengkap cara mengisi file konfigurasi mapping untuk menghubungkan PIKAS dengan Google Spreadsheet. Ini adalah dokumen yang **wajib dipahami** oleh setiap administrator sistem.

---

## Daftar Isi

1. [Konsep Dasar: Mapping sebagai Jembatan](#1-konsep-dasar)
2. [File `mapping.json` — Konfigurasi IKU](#2-file-mappingjson)
3. [Cara Menemukan Koordinat Cell](#3-cara-menemukan-koordinat-cell)
4. [Referensi Kunci Mapping](#4-referensi-kunci-mapping)
5. [File `ro-mapping.json` — Konfigurasi Master RO](#5-file-ro-mappingjson)
6. [Alur Kerja Konfigurasi Lengkap](#6-alur-kerja-konfigurasi-lengkap)
7. [Kesalahan Umum dan Solusinya](#7-kesalahan-umum)

---

## 1. Konsep Dasar

PIKAS tidak memiliki database yang terpisah dari kertas kerja Anda. Sistem ini membaca dan menulis langsung ke Google Spreadsheet yang sudah ada, dengan memetakan setiap kolom di spreadsheet ke sebuah fungsi di dalam PIKAS.

**Analogi**: `mapping.json` adalah "peta" yang memberi tahu PIKAS: *"Jika kamu ingin tahu nilai target IKU 1.1.1.1, lihat di Sheet 'Monitoring', kolom K, baris 15."*

```
mapping.json                    Google Spreadsheet
────────────────                ────────────────────
"kode": "1.1.1.1"    ────►     Baris data IKU 1.1.1.1
"target": "K15"      ────►     Cell K15 = nilai target
"realisasi_tw1":"Q15"────►     Cell Q15 = realisasi TW1
```

---

## 2. File `mapping.json`

File ini adalah konfigurasi utama untuk seluruh IKU yang dipantau. File ini **diunggah melalui antarmuka Admin** di halaman Konfigurasi Kertas Kerja.

### Struktur Dasar

```json
{
    "spreadsheet_id": "ID_GOOGLE_SPREADSHEET_ANDA",
    "sheet_name": "NamaSheet",
    "ikus": [
        {
            "kode": "1.1.1.1",
            "cells": {
                "target": "K15",
                "realisasi_tw1": "Q15",
                ...
            }
        }
    ]
}
```

### Keterangan Field Level Atas

| Field | Tipe | Wajib | Keterangan |
|---|---|---|---|
| `spreadsheet_id` | String | ✅ | ID Google Spreadsheet. Ambil dari URL: `docs.google.com/spreadsheets/d/**[ID_INI]**/edit` |
| `sheet_name` | String | ✅ | Nama tab/sheet yang berisi data IKU (peka huruf besar/kecil) |
| `ikus` | Array | ✅ | Daftar semua IKU beserta koordinat cell-nya |

---

## 3. Cara Menemukan Koordinat Cell

Koordinat cell menggunakan format **Kolom-Baris** dari Google Sheets, misalnya: `K15`, `AE79`, `AB103`.

**Langkah-langkah**:
1. Buka Google Spreadsheet yang menjadi kertas kerja.
2. Klik pada cell yang ingin Anda petakan.
3. Lihat **Name Box** di pojok kiri atas (biasanya menampilkan nama cell seperti `K15`).
4. Salin koordinat tersebut ke field yang sesuai di `mapping.json`.

```
┌──────────────────────────────────────────┐
│  K15  │ ◄── Name Box (koordinat cell)    │
├───┬───┼──────────────────────────────────┤
│   │   │  A  │  B  │ ... │  K  │ ...      │
├───┼───┼──────────────────────────────────┤
│15 │   │     │     │     │  🎯 │           │
└───┴───┴──────────────────────────────────┘
                              ↑ Cell K15
```

> **Penting**: Pastikan koordinat cell yang Anda masukkan adalah koordinat **nilai akhirnya** (yang sudah terkalkulasi formula), bukan koordinat cell yang berisi formula itu sendiri, kecuali Anda memang ingin mengambil teks formulanya.

---

## 4. Referensi Kunci Mapping

Berikut adalah seluruh kunci yang dapat digunakan dalam objek `cells` untuk setiap IKU.

### Metadata IKU (PULL ONLY — Hanya baca dari GSheet)

| Kunci | Tipe Data | Keterangan |
|---|---|---|
| `kode_indikator` | String | Kode IKU (misal: `1.1.1.1`) |
| `tujuan` | String | Deskripsi tujuan strategis |
| `kode_tujuan` | String | Kode tujuan (misal: `1`) |
| `sasaran` | String | Deskripsi sasaran program |
| `kode_sasaran` | String | Kode sasaran (misal: `1.1`) |
| `indikator` | String | Nama lengkap IKU |
| `jenis_iku` | String | Nilai: `IKU` atau `PROKSI` |
| `jenis_periode` | String | Nilai: `TAHUNAN` atau `TRIWULANAN` |
| `jenis_persen` | Boolean | `true` jika satuan persen |
| `satuan` | String | Satuan pengukuran (misal: `Persen`, `Dokumen`) |
| `target` | Angka | Target tahunan IKU |

### Target Alokasi Triwulanan (PULL ONLY)

| Kunci | Keterangan |
|---|---|
| `alokasi_target_tw1` | Alokasi target Triwulan I |
| `alokasi_target_tw2` | Alokasi target Triwulan II |
| `alokasi_target_tw3` | Alokasi target Triwulan III |
| `alokasi_target_tw4` | Alokasi target Triwulan IV |

### Realisasi Triwulanan (TWO_WAY — Baca & Tulis)

| Kunci | Keterangan |
|---|---|
| `realisasi_tw1` | Realisasi Triwulan I |
| `realisasi_tw2` | Realisasi Triwulan II |
| `realisasi_tw3` | Realisasi Triwulan III |
| `realisasi_tw4` | Realisasi Triwulan IV |

### Capaian Periodik (PULL ONLY)

| Kunci | Keterangan |
|---|---|
| `capaian_tw_tw1` s/d `capaian_tw_tw4` | Capaian per triwulan (relatif terhadap alokasi) |
| `capaian_tahunan_tw1` s/d `capaian_tahunan_tw4` | Capaian kumulatif tahunan |

### Data Tindak Lanjut (TWO_WAY — Baca & Tulis)

| Kunci | Keterangan |
|---|---|
| `kendala` | Uraian kendala yang dihadapi |
| `solusi` | Uraian solusi yang diterapkan |
| `rtl` | Rencana Tindak Lanjut |
| `pic_rtl` | Penanggung jawab RTL |
| `batas_waktu_rtl` | Batas waktu RTL |

### Bukti & Tautan (TWO_WAY)

| Kunci | Keterangan |
|---|---|
| `link_bukti_kinerja` | Tautan folder bukti kinerja di Google Drive |
| `link_solusi` | Tautan dokumentasi solusi |
| `link_bukti_tl_sebelumnya` | Tautan bukti tindak lanjut periode sebelumnya |

### PKO & Nilai Akhir (PULL ONLY)

| Kunci | Keterangan |
|---|---|
| `pko_normalisasi` | Nilai normalisasi PKO |
| `pko_koreksi_akip` | Koreksi AKIP |
| `pko_nilai_akhir` | Nilai PKO akhir |

### Konfigurasi IKU Proksi (Jika `jenis_iku = "PROKSI"`)

Jika IKU menggunakan metode proksi (penghitungan X/Y), tambahkan kunci-kunci berikut:

| Kunci | Keterangan |
|---|---|
| `proksi_x` | Label / koordinat data sumber X |
| `proksi_y` | Label / koordinat data sumber Y |
| `proksi_x_target_tw1` s/d `_tw4` | Target X per triwulan |
| `proksi_y_target_tw1` s/d `_tw4` | Target Y per triwulan |
| `proksi_x_realisasi_tw1` s/d `_tw4` | Realisasi X per triwulan |
| `proksi_y_realisasi_tw1` s/d `_tw4` | Realisasi Y per triwulan |
| `proksi_x_target_tahunan` | Target X kumulatif tahunan |
| `proksi_y_target_tahunan` | Target Y kumulatif tahunan |

> **Catatan**: Untuk IKU non-proksi, isi field proksi dengan string kosong `""`.

---

## 5. File `ro-mapping.json`

File ini adalah **template awal** untuk diisi di Monaco JSON Editor pada halaman **Master RO**. Gunakan file ini sebagai referensi format sebelum mengunggah ke PIKAS via fitur Sync.

### Struktur

```json
[
    {
        "kode_iku": "1.1.1.1",
        "kode_ro": "2905 BMA 004",
        "nama_ro": "Publikasi/Laporan Survei Angkatan Kerja Nasional",
        "kegiatan": "1. SAKERNAS\n2. SUSENAS"
    }
]
```

### Keterangan Field

| Field | Tipe | Wajib | Keterangan |
|---|---|---|---|
| `kode_iku` | String | ✅ | Kode IKU yang menaungi RO ini. Pisahkan dengan koma jika RO masuk ke beberapa IKU (misal: `"1.1.1.1, 1.1.2.1"`) |
| `kode_ro` | String | ✅ | Kode Rincian Output (misal: `2905 BMA 004`). Harus unik dalam satu tahun kerja |
| `nama_ro` | String | ✅ | Nama lengkap Rincian Output |
| `kegiatan` | String | | Daftar kegiatan pendukung RO. Gunakan `\n` untuk memisahkan antar kegiatan |

### Aturan Penting

1. **Satu RO, Banyak IKU**: Jika satu RO menaungi lebih dari satu IKU, masukkan semua kode IKU dalam field `kode_iku` dipisahkan dengan koma.
   ```json
   { "kode_iku": "1.1.1.1, 1.1.3.1", "kode_ro": "2905 BMA 004", ... }
   ```

2. **Satu IKU, Banyak RO**: Buat entri terpisah untuk setiap RO dengan `kode_iku` yang sama.
   ```json
   { "kode_iku": "1.1.3.1", "kode_ro": "2906 BMA 005", ... },
   { "kode_iku": "1.1.3.1", "kode_ro": "2906 BMA 006", ... }
   ```

3. **Full-Sync**: Proses Sync bersifat destruktif terhadap data lama. RO yang ada di database tapi tidak ada di JSON **akan dihapus**. Pastikan JSON yang disinkronkan selalu berisi data yang lengkap dan benar.

4. **Tidak Perlu Whitespace**: Kode RO akan di-*trim* otomatis oleh sistem untuk mencegah duplikasi akibat spasi yang tidak sengaja.

---

## 6. Alur Kerja Konfigurasi Lengkap

Ikuti langkah-langkah ini secara berurutan saat pertama kali mengkonfigurasi periode baru.

```
Langkah 1: Siapkan mapping.json
        │
        │  Isi spreadsheet_id, sheet_name,
        │  dan koordinat cell setiap IKU.
        ▼
Langkah 2: Upload ke Kertas Kerja
        │
        │  Admin → Kertas Kerja → Pilih Periode
        │  → Config JSON → Paste/Upload mapping.json
        ▼
Langkah 3: Lakukan PULL pertama
        │
        │  Admin → Kertas Kerja → Pilih Periode
        │  → Klik tombol "Pull Data"
        ▼
Langkah 4: Verifikasi data di Dashboard
        │
        │  Pastikan nilai target, satuan, dan
        │  metadata IKU sudah terbaca dengan benar.
        ▼
Langkah 5: Siapkan dan Sync Master RO
        │
        │  Admin → Master RO → Pilih Tahun
        │  → Edit JSON di Monaco Editor → Klik "Sync RO"
        ▼
Langkah 6: Assign Operator ke IKU
        │
        │  Admin → Pengguna → Edit Operator
        │  → Tetapkan IKU yang menjadi tanggung jawabnya
        ▼
Selesai. Sistem siap digunakan.
```

---

## 7. Kesalahan Umum

| Error | Penyebab | Solusi |
|---|---|---|
| `400 Malformed Request` | Jumlah IKU terlalu banyak (URL terlalu panjang) | Sistem sudah menangani ini dengan chunking. Pastikan versi kode terbaru digunakan. |
| `403 Permission Denied` | Service Account tidak memiliki akses ke spreadsheet | Bagikan spreadsheet ke email Service Account dengan minimal izin "Viewer" untuk PULL, atau "Editor" untuk PUSH. |
| `404 Not Found` saat PULL | `sheet_name` salah | Pastikan nama sheet di `mapping.json` persis sama dengan nama tab di Google Spreadsheet (peka huruf besar/kecil dan spasi). |
| Data tidak terupdate setelah PULL | `is_dirty = True` | Operator sudah menyimpan data tersebut. PULL tidak akan menimpa data yang sudah diisi. Reset `is_dirty` melalui admin jika diperlukan. |
| RO terhapus setelah Sync | JSON tidak lengkap | Pastikan JSON yang disinkronkan berisi **semua** RO yang diinginkan, bukan hanya yang baru ditambahkan. |
| Duplikasi RO | Spasi tersembunyi di `kode_ro` | Sistem akan otomatis men-*strip* whitespace. Jika masih terjadi, periksa apakah ada karakter khusus di kode RO. |

---

*Dokumen ini adalah bagian dari dokumentasi resmi PIKAS.*
*Copyright (c) 2026 Ilham Rizanto. Seluruh hak cipta dilindungi.*
