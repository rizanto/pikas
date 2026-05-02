# Kebijakan Keamanan PIKAS

> **Copyright (c) 2026 Ilham Rizanto. Seluruh hak cipta dilindungi.**

## Melaporkan Celah Keamanan

Jika Anda menemukan celah keamanan pada perangkat lunak PIKAS, **jangan** melaporkannya melalui isu publik (*public issue*) di GitHub. Hal ini dapat membahayakan sistem yang sedang berjalan di lingkungan produksi sebelum ada perbaikan yang tersedia.

Laporkan kerentanan keamanan secara bertanggung jawab (*responsible disclosure*) dengan menghubungi pemilik secara langsung melalui profil GitHub:

**https://github.com/ilhamrizanto**

Sertakan informasi berikut dalam laporan Anda:
- Deskripsi singkat dan jelas tentang kerentanan
- Langkah-langkah untuk mereproduksi masalah
- Dampak potensial yang mungkin ditimbulkan
- Saran perbaikan (jika ada)

Kami berkomitmen untuk merespons laporan keamanan dalam waktu **5 hari kerja** dan bekerja sama dengan pelapor untuk menyelesaikan masalah sebelum pengungkapan publik.

---

## Praktik Keamanan yang Diterapkan

- Seluruh komunikasi antara backend dan Google Sheets menggunakan autentikasi **Service Account OAuth2**.
- Tidak ada data kredensial (API key, password) yang boleh di-*commit* ke repositori.
- Kontrol akses berbasis peran (RBAC) diterapkan pada setiap endpoint dan tampilan.
- File `.env` dan `service_account.json` dikecualikan secara eksplisit melalui `.gitignore`.

---

*Copyright (c) 2026 Ilham Rizanto. Seluruh hak cipta dilindungi.*
