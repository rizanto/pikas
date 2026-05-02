# =============================================================================
# PIKAS — Performance Indicators Knowledgebase Accountability System
# File    : services/gsheet_service.py
# Author  : Ilham Rizanto
# Copyright (c) 2026 Ilham Rizanto. All Rights Reserved.
# Unauthorized use, reproduction, or distribution is strictly prohibited.
# See LICENSE file for full terms.
# =============================================================================
import re
import gspread
from django.conf import settings
from google.oauth2.service_account import Credentials
from pikas_app.models import MasterIKU, FRAEntry
from django.utils import timezone
from django.db import transaction

import os
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", str(settings.BASE_DIR / 'service_account.json'))
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Fields yang TWO_WAY (operator bisa edit → Push kembali ke GSheet)
TWO_WAY_FIELDS = {
    'realisasi_tw1', 'realisasi_tw2', 'realisasi_tw3', 'realisasi_tw4',
    'kendala', 'solusi', 'rtl', 'pic_rtl', 'batas_waktu_rtl',
    'link_bukti_kinerja', 'link_bukti_tl_sebelumnya', 'link_solusi',
    'proksi_x_realisasi_tw1', 'proksi_x_realisasi_tw2',
    'proksi_x_realisasi_tw3', 'proksi_x_realisasi_tw4',
    'proksi_y_realisasi_tw1', 'proksi_y_realisasi_tw2',
    'proksi_y_realisasi_tw3', 'proksi_y_realisasi_tw4',
}

# Mapping dari cell key → FRAEntry field (untuk TWO_WAY fields yg punya kolom sendiri)
ENTRY_FIELD_MAP = {
    'kendala': 'kendala',
    'solusi': 'solusi',
    'rtl': 'rtl',
    'pic_rtl': 'pic_rtl',
    'batas_waktu_rtl': 'batas_waktu_rtl',
    'link_bukti_kinerja': 'link_bukti_kinerja',
    'link_bukti_tl_sebelumnya': 'link_bukti_tl_sebelumnya',
    'link_solusi': 'link_solusi',
}


import json

def get_gspread_client():
    # Cek apakah ada JSON langsung di env var (untuk kemudahan di VPS/Dokploy)
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        try:
            info = json.loads(sa_json)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception as e:
            raise ValueError(f"Error parsing GOOGLE_SERVICE_ACCOUNT_JSON: {str(e)}")
    else:
        # Fallback ke file fisik
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            raise FileNotFoundError(f"Service account file not found at {SERVICE_ACCOUNT_FILE} and GOOGLE_SERVICE_ACCOUNT_JSON env var is empty.")
        creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_FILE), scopes=SCOPES)
    
    return gspread.authorize(creds)


def sanitize_for_gsheet(text):
    if not text:
        return ""
    clean = re.compile('<.*?>')
    cleaned_text = re.sub(clean, '', str(text))
    return cleaned_text.replace('\r\n', '\n')


@transaction.atomic
def pull_periode_data(gsheet_id, periode, ignore_dirty=False, only_done=False):
    """
    Pull data dari GSheet untuk periode tertentu.
    """
    client = get_gspread_client()
    try:
        spreadsheet = client.open_by_key(gsheet_id)
    except Exception as e:
        raise ValueError(f"Could not open spreadsheet {gsheet_id}: {str(e)}")

    sheet_name = periode.sheet_name
    ikus_query = MasterIKU.objects.filter(periode=periode)
    
    # Jika only_done=True, kita hanya memproses IKU yang entry-nya sudah is_done
    if only_done:
        ikus_query = ikus_query.filter(entry__is_done=True).distinct()

    ikus = list(ikus_query)
    if not ikus:
        return

    # Collect ALL ranges to fetch in batch
    ranges_to_fetch = []
    # Quote sheet name if it contains spaces or special characters
    safe_sheet_name = f"'{sheet_name}'" if " " in sheet_name or "!" in sheet_name else sheet_name

    for iku in ikus:
        cells = iku.cells or {}
        for key, coord in cells.items():
            if coord and isinstance(coord, str) and coord.strip():
                rng = f"{safe_sheet_name}!{coord.strip()}"
                if rng not in ranges_to_fetch:
                    ranges_to_fetch.append(rng)

    if not ranges_to_fetch:
        return

    fetched_data = {}
    # Chunking: Ambil per 100 range untuk menghindari URL too long (Error 400)
    CHUNK_SIZE = 100
    for i in range(0, len(ranges_to_fetch), CHUNK_SIZE):
        chunk = ranges_to_fetch[i:i + CHUNK_SIZE]
        try:
            values_response = spreadsheet.values_batch_get(
                chunk, 
                params={'valueRenderOption': 'FORMATTED_VALUE'}
            )
            valueRanges = values_response.get('valueRanges', [])
            for j, rng_str in enumerate(chunk):
                if j < len(valueRanges):
                    vals = valueRanges[j].get('values', [])
                    val = vals[0][0] if vals and vals[0] else None
                    fetched_data[rng_str] = val
        except Exception as e:
            raise ValueError(f"Failed to batch_get chunk {i//CHUNK_SIZE + 1}: {str(e)}")

    entries_to_update = []
    tw = periode.triwulan

    for iku in ikus:
        cells = iku.cells or {}
        entry, _ = FRAEntry.objects.get_or_create(iku=iku)

        def get_val(key):
            coord = cells.get(key, '')
            if not coord or not coord.strip():
                return None
            return fetched_data.get(f"{safe_sheet_name}!{coord.strip()}")

        # Update metadata MasterIKU (Selalu diupdate jika ada perubahan di GSheet)
        meta_map = {
            'tujuan': cells.get('tujuan'),
            'kode_tujuan': cells.get('kode_tujuan'),
            'sasaran': cells.get('sasaran'),
            'kode_sasaran': cells.get('kode_sasaran'),
            'indikator': cells.get('indikator'),
            'satuan': cells.get('satuan'),
            'target': cells.get('target'),
            'jenis_iku': cells.get('jenis_iku'),
            'jenis_periode': cells.get('jenis_periode'),
            'proxy_x_label': cells.get('proksi_x'),
            'proxy_y_label': cells.get('proksi_y'),
        }
        meta_updated = False
        for field, cell_coord in meta_map.items():
            if cell_coord and isinstance(cell_coord, str):
                # Gunakan .strip() agar match dengan key di fetched_data
                val = fetched_data.get(f"{sheet_name}!{cell_coord.strip()}")
                if val is not None and str(val).strip() != str(getattr(iku, field)):
                    setattr(iku, field, str(val).strip())
                    meta_updated = True
        if meta_updated:
            iku.save()

        # Update FRAEntry
        # Jika ignore_dirty=True (saat Push & Sync), kita timpa semuanya.
        # Jika ignore_dirty=False (saat Pull Global), kita hanya timpa jika is_dirty=False.
        if ignore_dirty or not entry.is_dirty:
            # 1. Update Realisasi
            val_r = get_val(f'realisasi_tw{tw}')
            if val_r is not None:
                entry.realisasi = str(val_r)

            # 2. Update Narrative Fields
            for cell_key, entry_field in ENTRY_FIELD_MAP.items():
                val = get_val(cell_key)
                if val is not None:
                    setattr(entry, entry_field, str(val))

            # 3. Update Proxy
            if iku.has_proxy:
                val_px = get_val(f'proksi_x_realisasi_tw{tw}')
                val_py = get_val(f'proksi_y_realisasi_tw{tw}')
                if val_px is not None: entry.proksi_x_realisasi = str(val_px)
                if val_py is not None: entry.proksi_y_realisasi = str(val_py)

            # Jika ini adalah proses Sync setelah Push, maka kita reset is_dirty
            if ignore_dirty:
                entry.is_dirty = False

        entry.pulled_data = {k: get_val(k) for k in cells if get_val(k) is not None}
        entry.last_synced_at = timezone.now()
        entries_to_update.append(entry)

    if entries_to_update:
        FRAEntry.objects.bulk_update(entries_to_update, [
            'realisasi', 'kendala', 'solusi', 'rtl', 'pic_rtl', 'batas_waktu_rtl',
            'link_bukti_kinerja', 'link_bukti_tl_sebelumnya', 'link_solusi',
            'proksi_x_realisasi', 'proksi_y_realisasi', 'is_dirty', 'pulled_data', 'last_synced_at'
        ])


def push_periode_data(gsheet_id, periode):
    """
    Push & Sync: Push data IKU yang 'is_done' ke GSheet, 
    lalu tarik kembali (SYNC) untuk mendapatkan nilai kalkulasi terbaru.
    """
    client = get_gspread_client()
    try:
        spreadsheet = client.open_by_key(gsheet_id)
    except Exception as e:
        raise ValueError(f"Could not open spreadsheet {gsheet_id}: {str(e)}")

    # Hanya PUSH entri yang sudah TANDAI SELESAI
    entries = FRAEntry.objects.filter(
        iku__periode=periode,
        is_done=True
    ).select_related('iku')

    if not entries.exists():
        raise ValueError("Tidak ada data IKU berstatus 'Selesai' untuk di-Push.")

    batch_data = []
    sheet_name = periode.sheet_name
    safe_sheet_name = f"'{sheet_name}'" if " " in sheet_name or "!" in sheet_name else sheet_name
    tw = periode.triwulan

    for entry in entries:
        cells = entry.iku.cells or {}

        field_push_map = {
            'kendala': entry.kendala,
            'solusi': entry.solusi,
            'rtl': entry.rtl,
            'pic_rtl': entry.pic_rtl,
            'batas_waktu_rtl': entry.batas_waktu_rtl,
        }

        # Push realisasi for active TW ONLY IF NO PROXY
        if not entry.iku.has_proxy:
            realisasi_key = f'realisasi_tw{tw}'
            field_push_map[realisasi_key] = entry.realisasi

        # Push proxy realisasi if applicable
        if entry.iku.has_proxy:
            field_push_map[f'proksi_x_realisasi_tw{tw}'] = entry.proksi_x_realisasi
            field_push_map[f'proksi_y_realisasi_tw{tw}'] = entry.proksi_y_realisasi

        for field_key, value in field_push_map.items():
            coord = cells.get(field_key, '')
            if not coord or not coord.strip():
                continue
            val = sanitize_for_gsheet(value) if isinstance(value, str) else (value or '')
            batch_data.append({
                'range': f"{safe_sheet_name}!{coord.strip()}",
                'values': [[val]]
            })

    if batch_data:
        try:
            body = {
                'valueInputOption': 'USER_ENTERED',
                'data': batch_data
            }
            spreadsheet.values_batch_update(body)
        except Exception as e:
            raise ValueError(f"Failed to batch_update to Google Sheets: {str(e)}")

    # LANGKAH SYNC: Tarik kembali data dari GSheet untuk meng-update hasil kalkulasi (formula)
    # ignore_dirty=True agar menimpa isian lokal & me-reset flag 'Edited'
    pull_periode_data(gsheet_id, periode, ignore_dirty=True, only_done=True)
