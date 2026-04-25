import re
import gspread
from django.conf import settings
from google.oauth2.service_account import Credentials
from pikas_app.models import MasterIKU, FRAEntry
from django.utils import timezone
from django.db import transaction

SERVICE_ACCOUNT_FILE = settings.BASE_DIR / 'service_account.json'
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


def get_gspread_client():
    creds = Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_FILE), scopes=SCOPES)
    return gspread.authorize(creds)


def sanitize_for_gsheet(text):
    if not text:
        return ""
    clean = re.compile('<.*?>')
    cleaned_text = re.sub(clean, '', str(text))
    return cleaned_text.replace('\r\n', '\n')


@transaction.atomic
def pull_periode_data(gsheet_id, periode):
    """
    Pull data dari GSheet untuk periode tertentu.
    Membaca cell mapping dari setiap MasterIKU.cells
    """
    client = get_gspread_client()
    try:
        spreadsheet = client.open_by_key(gsheet_id)
    except Exception as e:
        raise ValueError(f"Could not open spreadsheet {gsheet_id}: {str(e)}")

    sheet_name = periode.sheet_name
    ikus = MasterIKU.objects.filter(periode=periode)

    # Collect ALL ranges to fetch in batch
    ranges_to_fetch = []
    for iku in ikus:
        cells = iku.cells or {}
        for key, coord in cells.items():
            if coord and isinstance(coord, str) and coord.strip():
                rng = f"{sheet_name}!{coord.strip()}"
                if rng not in ranges_to_fetch:
                    ranges_to_fetch.append(rng)

    if not ranges_to_fetch:
        return

    try:
        values_response = spreadsheet.values_batch_get(ranges_to_fetch)
    except Exception as e:
        raise ValueError(f"Failed to batch_get from Google Sheets: {str(e)}")

    valueRanges = values_response.get('valueRanges', [])
    fetched_data = {}
    for i, rng_str in enumerate(ranges_to_fetch):
        if i < len(valueRanges):
            vals = valueRanges[i].get('values', [])
            val = vals[0][0] if vals and vals[0] else None
            fetched_data[rng_str] = val

    entries_to_update = []

    for iku in ikus:
        cells = iku.cells or {}
        entry, _ = FRAEntry.objects.get_or_create(iku=iku)

        def get_val(key):
            coord = cells.get(key, '')
            if not coord or not coord.strip():
                return None
            return fetched_data.get(f"{sheet_name}!{coord.strip()}")

        # Build pulled_data dict (ALL fields from GSheet)
        pulled = {}
        for key in cells:
            val = get_val(key)
            if val is not None:
                pulled[key] = val

        # Metadata sync (Optional: Update MasterIKU fields if cell is mapped)
        meta_updated = False
        meta_map = {
            'tujuan': cells.get('tujuan'),
            'kode_tujuan': cells.get('kode_tujuan'),
            'sasaran': cells.get('sasaran'),
            'kode_sasaran': cells.get('kode_sasaran'),
            'indikator': cells.get('indikator'),
            'satuan': cells.get('satuan'),
            'jenis_iku': cells.get('jenis_iku'),
            'jenis_periode': cells.get('jenis_periode'),
            'jenis_persen': cells.get('jenis_persen'),
            'proxy_x_label': cells.get('proksi_x'),
            'proxy_y_label': cells.get('proksi_y'),
        }
        
        for field, cell_coord in meta_map.items():
            if cell_coord and f"{sheet_name}!{cell_coord}" in fetched_data:
                val = str(fetched_data[f"{sheet_name}!{cell_coord}"]).strip()
                
                # Handle Boolean conversion for jenis_persen
                if field == 'jenis_persen':
                    # True if contains '%', False if contains 'non' or doesn't have '%'
                    clean_val = val.lower()
                    bool_val = '%' in clean_val and 'non' not in clean_val
                    if bool_val != getattr(iku, field):
                        setattr(iku, field, bool_val)
                        meta_updated = True
                elif val != getattr(iku, field):
                    setattr(iku, field, val)
                    meta_updated = True
        
        if meta_updated:
            iku.save()

        # Update FRAEntry pulled_data
        entry.pulled_data = pulled

        # TWO_WAY Fields → only overwrite if NOT dirty (operator hasn't edited yet)
        if not entry.is_dirty:
            for cell_key, entry_field in ENTRY_FIELD_MAP.items():
                val = get_val(cell_key)
                if val is not None:
                    setattr(entry, entry_field, str(val))

            # Realisasi for active TW
            tw = periode.triwulan
            realisasi_key = f'realisasi_tw{tw}'
            val_r = get_val(realisasi_key)
            if val_r is not None:
                entry.realisasi = str(val_r)

            if iku.has_proxy:
                val_px = get_val(f'proksi_x_realisasi_tw{tw}')
                val_py = get_val(f'proksi_y_realisasi_tw{tw}')
                if val_px is not None:
                    entry.proksi_x_realisasi = str(val_px)
                if val_py is not None:
                    entry.proksi_y_realisasi = str(val_py)

        entry.last_synced_at = timezone.now()
        entries_to_update.append(entry)

    if entries_to_update:
        FRAEntry.objects.bulk_update(entries_to_update, [
            'pulled_data', 'kendala', 'solusi', 'rtl', 'pic_rtl',
            'batas_waktu_rtl', 'link_bukti_kinerja', 'link_bukti_tl_sebelumnya',
            'link_solusi', 'realisasi', 'proksi_x_realisasi', 'proksi_y_realisasi',
            'last_synced_at'
        ])


def push_periode_data(gsheet_id, periode):
    """
    Push TWO_WAY data ke GSheet untuk periode tertentu.
    """
    client = get_gspread_client()
    try:
        spreadsheet = client.open_by_key(gsheet_id)
    except Exception as e:
        raise ValueError(f"Could not open spreadsheet {gsheet_id}: {str(e)}")

    entries = FRAEntry.objects.filter(
        iku__periode=periode
    ).select_related('iku')

    batch_data = []
    sheet_name = periode.sheet_name
    tw = periode.triwulan

    for entry in entries:
        cells = entry.iku.cells or {}

        # Push narrative/link fields
        field_push_map = {
            'kendala': entry.kendala,
            'solusi': entry.solusi,
            'rtl': entry.rtl,
            'pic_rtl': entry.pic_rtl,
            'batas_waktu_rtl': entry.batas_waktu_rtl,
            'link_bukti_kinerja': entry.link_bukti_kinerja,
            'link_bukti_tl_sebelumnya': entry.link_bukti_tl_sebelumnya,
            'link_solusi': entry.link_solusi,
        }

        # Push realisasi for active TW
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
                'range': f"{sheet_name}!{coord.strip()}",
                'values': [[val]]
            })

    if not batch_data:
        return

    try:
        spreadsheet.values_batch_update(batch_data)
    except Exception as e:
        raise ValueError(f"Failed to batch_update to Google Sheets: {str(e)}")
