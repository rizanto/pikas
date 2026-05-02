# =============================================================================
# PIKAS — Performance Indicators Knowledgebase Accountability System
# File    : views.py
# Author  : Ilham Rizanto
# Copyright (c) 2026 Ilham Rizanto. All Rights Reserved.
# Unauthorized use, reproduction, or distribution is strictly prohibited.
# See LICENSE file for full terms.
# =============================================================================
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout as auth_logout
from .models import AppConfig, PeriodeKertasKerja, MasterIKU, FRAEntry, CustomUser
from .decorators import role_required
from django.contrib.auth.hashers import make_password


def get_active_config():
    return AppConfig.objects.select_related('active_periode').first()


def attach_previous_rtl(entries, periode):
    """Efisiensi: Menarik semua RTL periode sebelumnya sekaligus untuk daftar entry."""
    prev_q = periode.triwulan - 1
    prev_y = periode.tahun
    if prev_q < 1:
        prev_q = 4
        prev_y -= 1
    
    try:
        prev_periode = PeriodeKertasKerja.objects.get(tahun=prev_y, triwulan=prev_q)
        prev_entries = FRAEntry.objects.filter(iku__periode=prev_periode).values('iku__kode_indikator', 'rtl')
        rtl_map = {item['iku__kode_indikator']: item['rtl'] for item in prev_entries}
        
        for entry in entries:
            entry.previous_rtl = rtl_map.get(entry.iku.kode_indikator, "")
    except PeriodeKertasKerja.DoesNotExist:
        for entry in entries:
            entry.previous_rtl = ""
    return entries


# ============================================================
# AUTH
# ============================================================
@login_required
def logout_view(request):
    auth_logout(request)
    return redirect('login')


# ============================================================
# DASHBOARD
# ============================================================
@login_required
def dashboard_view(request):
    config = get_active_config()
    periodes = PeriodeKertasKerja.objects.all().order_by('-tahun', '-triwulan')
    
    periode_id = request.GET.get('periode')
    if periode_id:
        periode = get_object_or_404(PeriodeKertasKerja, id=periode_id)
    else:
        periode = config.active_periode if config else None

    if not periode:
        if request.user.role == 'ADMIN':
            return redirect('kertas_kerja')
        return render(request, 'dashboard.html', {
            'error': 'Sistem belum dikonfigurasi. Hubungi Admin untuk melakukan setup awal.'
        })

    entries = FRAEntry.objects.filter(
        iku__periode=periode
    ).select_related('iku', 'pic_tim_kerja').order_by('iku__kode_indikator')

    total_iku = entries.count()
    done_iku = entries.filter(is_done=True).count()
    pending_iku = total_iku - done_iku

    # Operator progress
    operators = CustomUser.objects.filter(role='OPERATOR')
    operator_progress = []
    for op in operators:
        op_entries = entries.filter(pic_tim_kerja=op)
        op_total = op_entries.count()
        if op_total > 0:
            op_done = op_entries.filter(is_done=True).count()
            operator_progress.append({
                'user': op,
                'total': op_total,
                'done': op_done,
                'pending': op_total - op_done,
                'percent': int((op_done / op_total) * 100) if op_total > 0 else 0
            })
    
    # Sort operator progress by pending count descending
    operator_progress.sort(key=lambda x: x['pending'], reverse=True)

    return render(request, 'dashboard.html', {
        'periode': periode,
        'periodes': periodes,
        'entries': entries,
        'total_iku': total_iku,
        'done_iku': done_iku,
        'pending_iku': pending_iku,
        'operator_progress': operator_progress,
    })


@login_required
def dashboard_review_view(request, entry_id):
    target_entry = get_object_or_404(FRAEntry.objects.select_related('iku', 'pic_tim_kerja', 'iku__periode'), id=entry_id)
    periode = target_entry.iku.periode
    
    entries = FRAEntry.objects.filter(
        iku__periode=periode
    ).select_related('iku', 'pic_tim_kerja').order_by('iku__kode_indikator')
    
    # Attach previous RTL
    attach_previous_rtl(entries, periode)
    
    total = entries.count()
    done = entries.filter(is_done=True).count()
    
    return render(request, 'dashboard_review.html', {
        'periode': periode,
        'entries': entries,
        'total': total,
        'done': done,
        'target_entry_id': str(target_entry.id),
    })


# ============================================================
# PENGGUNA
# ============================================================
@login_required
@role_required(['ADMIN'])
def pengguna_view(request):
    users = CustomUser.objects.all().order_by('username')
    return render(request, 'pengguna.html', {'users': users})


@csrf_exempt
@login_required
@role_required(['ADMIN'])
def api_manage_user(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        action = data.get('action')

        if action == 'create':
            if CustomUser.objects.filter(username=data.get('username')).exists():
                return JsonResponse({'error': 'Username sudah ada.'}, status=400)
            user = CustomUser.objects.create(
                username=data.get('username'),
                first_name=data.get('first_name', ''),
                role=data.get('role', 'OPERATOR')
            )
            user.set_password(data.get('password'))
            user.save()
            return JsonResponse({'status': 'success', 'message': 'Pengguna berhasil dibuat.'})

        elif action == 'edit':
            user = CustomUser.objects.get(id=data.get('user_id'))
            user.username = data.get('username')
            user.first_name = data.get('first_name', '')
            user.role = data.get('role', 'OPERATOR')
            user.save()
            return JsonResponse({'status': 'success', 'message': 'Pengguna berhasil diupdate.'})

        elif action == 'reset_password':
            user = CustomUser.objects.get(id=data.get('user_id'))
            user.set_password(data.get('new_password'))
            user.save()
            return JsonResponse({'status': 'success', 'message': 'Password berhasil direset.'})

        elif action == 'delete':
            user = CustomUser.objects.get(id=data.get('user_id'))
            if user.is_superuser:
                return JsonResponse({'error': 'Tidak dapat menghapus Superuser.'}, status=400)
            user.delete()
            return JsonResponse({'status': 'success', 'message': 'Pengguna berhasil dihapus.'})

        return JsonResponse({'error': 'Unknown action'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ============================================================
# KERTAS KERJA — Halaman Utama (List Periode)
# ============================================================
@login_required
@role_required(['ADMIN'])
def kertas_kerja_view(request):
    periodes = PeriodeKertasKerja.objects.all()
    config = get_active_config()
    return render(request, 'kertas_kerja.html', {
        'periodes': periodes,
        'config': config,
    })


# ============================================================
# KERTAS KERJA — Sub-halaman: Konfigurasi Periode
# ============================================================
@login_required
@role_required(['ADMIN'])
def periode_config_view(request, periode_id):
    periode = get_object_or_404(PeriodeKertasKerja, id=periode_id)
    # We pass entries so we know the PIC for each IKU
    entries = FRAEntry.objects.filter(
        iku__periode=periode
    ).select_related('iku', 'pic_tim_kerja').order_by('iku__kode_indikator')
    
    operators = CustomUser.objects.filter(role='OPERATOR').order_by('username')
    
    # Serialize config_json properly for JavaScript consumption
    config_json_str = json.dumps(periode.config_json) if periode.config_json else 'null'
    return render(request, 'periode_config.html', {
        'periode': periode,
        'entries': entries,
        'operators': operators,
        'config_json_str': config_json_str,
    })


# ============================================================
# KERTAS KERJA — Sub-halaman: Review Compact
# ============================================================
@login_required
@role_required(['ADMIN'])
def periode_review_view(request, periode_id):
    periode = get_object_or_404(PeriodeKertasKerja, id=periode_id)
    entries = FRAEntry.objects.filter(
        iku__periode=periode
    ).select_related('iku', 'pic_tim_kerja').order_by('iku__kode_indikator')
    
    # Attach previous RTL
    attach_previous_rtl(entries, periode)
    
    total = entries.count()
    done = entries.filter(is_done=True).count()
    return render(request, 'periode_review.html', {
        'periode': periode,
        'entries': entries,
        'total': total,
        'done': done,
    })


# ============================================================
# API: Kertas Kerja (Periode CRUD, GSheet ID, Set Active)
# ============================================================
@csrf_exempt
@login_required
@role_required(['ADMIN'])
def api_kertas_kerja(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        action = data.get('action')

        if action == 'save_gsheet_id':
            config = get_active_config()
            if not config:
                config = AppConfig(gsheet_id=data.get('gsheet_id', ''))
            else:
                config.gsheet_id = data.get('gsheet_id', '')
            config.save()
            return JsonResponse({'status': 'success', 'message': 'GSheet ID berhasil disimpan.'})

        elif action == 'create_periode':
            tahun = int(data.get('tahun'))
            triwulan = int(data.get('triwulan'))
            sheet_name = data.get('sheet_name', f'{tahun}Q{triwulan}')

            if PeriodeKertasKerja.objects.filter(tahun=tahun, triwulan=triwulan).exists():
                return JsonResponse({'error': f'Periode {tahun} TW{triwulan} sudah ada.'}, status=400)

            PeriodeKertasKerja.objects.create(
                tahun=tahun, triwulan=triwulan, sheet_name=sheet_name
            )
            return JsonResponse({'status': 'success', 'message': f'Periode {tahun} TW{triwulan} berhasil dibuat.'})

        elif action == 'delete_periode':
            periode = PeriodeKertasKerja.objects.get(id=data.get('periode_id'))
            label = periode.label
            periode.delete()
            return JsonResponse({'status': 'success', 'message': f'Periode {label} berhasil dihapus.'})

        elif action == 'set_active':
            periode = PeriodeKertasKerja.objects.get(id=data.get('periode_id'))
            config = get_active_config()
            if not config:
                config = AppConfig(gsheet_id='')
            config.active_periode = periode
            config.save()
            return JsonResponse({'status': 'success', 'message': f'{periode.label} ditetapkan sebagai periode aktif.'})

        return JsonResponse({'error': 'Unknown action'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ============================================================
# API: Periode Config (Save JSON, Pull, Push, Lock)
# ============================================================
@csrf_exempt
@login_required
@role_required(['ADMIN'])
def api_periode_config(request, periode_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    periode = get_object_or_404(PeriodeKertasKerja, id=periode_id)

    try:
        data = json.loads(request.body)
        action = data.get('action')

        if action == 'save_json':
            raw = data.get('config_json', '{}')
            try:
                config_obj = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return JsonResponse({'error': 'Format JSON tidak valid.'}, status=400)

            # Validate structure
            if 'iku_list' not in config_obj or not isinstance(config_obj['iku_list'], list):
                return JsonResponse({'error': 'JSON harus memiliki key "iku_list" berupa array.'}, status=400)

            # Save config_json to period
            periode.config_json = config_obj
            periode.save(update_fields=['config_json'])

            # Sync MasterIKU records from JSON
            existing_kodes = set(periode.ikus.values_list('kode_indikator', flat=True))
            json_kodes = set()

            for iku_def in config_obj['iku_list']:
                kode = iku_def.get('kode', '').strip()
                if not kode:
                    continue
                json_kodes.add(kode)

                # Helper to handle potential coordinate strings in boolean fields
                def to_bool(val, default_val=True):
                    if isinstance(val, bool):
                        return val
                    return default_val

                iku_obj, created = MasterIKU.objects.update_or_create(
                    periode=periode,
                    kode_indikator=kode,
                    defaults={
                        'tujuan': iku_def.get('tujuan', iku_def.get('cells', {}).get('tujuan', '')),
                        'kode_tujuan': iku_def.get('kode_tujuan', iku_def.get('cells', {}).get('kode_tujuan', '')),
                        'sasaran': iku_def.get('sasaran', iku_def.get('cells', {}).get('sasaran', '')),
                        'kode_sasaran': iku_def.get('kode_sasaran', iku_def.get('cells', {}).get('kode_sasaran', '')),
                        'indikator': iku_def.get('indikator', iku_def.get('cells', {}).get('indikator', '')),
                        'jenis_iku': iku_def.get('jenis_iku', 'IKU'),
                        'jenis_periode': iku_def.get('jenis_periode', 'TRIWULANAN'),
                        'jenis_persen': to_bool(iku_def.get('jenis_persen', iku_def.get('cells', {}).get('jenis_persen', True))),
                        'satuan': iku_def.get('satuan', iku_def.get('cells', {}).get('satuan', '')),
                        'has_proxy': any(str(v).strip() for k, v in iku_def.get('cells', {}).items() if k.startswith('proksi_')),
                        'proxy_x_label': iku_def.get('proksi_x', iku_def.get('cells', {}).get('proksi_x', '')),
                        'proxy_y_label': iku_def.get('proksi_y', iku_def.get('cells', {}).get('proksi_y', '')),
                        'cells': iku_def.get('cells', {}),
                    }
                )
                FRAEntry.objects.get_or_create(iku=iku_obj)

            # Remove IKUs not in JSON anymore
            removed = existing_kodes - json_kodes
            if removed:
                MasterIKU.objects.filter(periode=periode, kode_indikator__in=removed).delete()

            periode.is_configured = len(json_kodes) > 0
            periode.save(update_fields=['is_configured'])

            return JsonResponse({'status': 'success', 'message': f'{len(json_kodes)} IKU berhasil disinkronkan dari JSON.'})

        elif action == 'toggle_lock':
            periode.is_locked = not periode.is_locked
            periode.save(update_fields=['is_locked'])
            status_text = 'dikunci' if periode.is_locked else 'dibuka'
            return JsonResponse({'status': 'success', 'message': f'Periode {periode.label} berhasil {status_text}.', 'is_locked': periode.is_locked})

        elif action == 'pull':
            from .services.gsheet_service import pull_periode_data
            config = get_active_config()
            if not config or not config.gsheet_id:
                return JsonResponse({'error': 'GSheet ID belum dikonfigurasi.'}, status=400)
            if not periode.config_json or not periode.config_json.get('iku_list'):
                return JsonResponse({'error': 'Config JSON belum diisi. Simpan JSON terlebih dahulu.'}, status=400)
            pull_periode_data(config.gsheet_id, periode)
            return JsonResponse({'status': 'success', 'message': f'PULL data dari GSheet berhasil untuk {periode.label}.'})

        elif action == 'push':
            from .services.gsheet_service import push_periode_data
            config = get_active_config()
            if not config or not config.gsheet_id:
                return JsonResponse({'error': 'GSheet ID belum dikonfigurasi.'}, status=400)
            push_periode_data(config.gsheet_id, periode)
            return JsonResponse({'status': 'success', 'message': f'PUSH & SYNC data ke GSheet berhasil untuk {periode.label}. Seluruh IKU selesai telah diperbarui.'})

        elif action == 'assign_pic':
            entry_id = data.get('entry_id')
            user_id = data.get('user_id')
            try:
                entry = FRAEntry.objects.get(id=entry_id, iku__periode=periode)
                if user_id:
                    user = CustomUser.objects.get(id=user_id, role='OPERATOR')
                    entry.pic_tim_kerja = user
                else:
                    entry.pic_tim_kerja = None
                entry.save(update_fields=['pic_tim_kerja'])
                pic_name = entry.pic_tim_kerja.username if entry.pic_tim_kerja else 'Belum Di-assign'
                return JsonResponse({'status': 'success', 'message': f'PIC berhasil diperbarui menjadi {pic_name}.'})
            except (FRAEntry.DoesNotExist, CustomUser.DoesNotExist) as e:
                return JsonResponse({'error': f'Gagal assign PIC: {str(e)}'}, status=400)

        return JsonResponse({'error': 'Unknown action'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ============================================================
# IKU WORKSPACE (Operator)
# ============================================================
@login_required
@role_required(['ADMIN', 'OPERATOR'])
def iku_list_view(request):
    config = get_active_config()
    periodes = PeriodeKertasKerja.objects.all().order_by('-tahun', '-triwulan')
    
    periode_id = request.GET.get('periode')
    if periode_id:
        periode = get_object_or_404(PeriodeKertasKerja, id=periode_id)
    else:
        periode = config.active_periode if config else None
        
    if not periode:
        return render(request, 'iku_list.html', {'error': 'Sistem belum dikonfigurasi.'})

    qs = FRAEntry.objects.filter(
        iku__periode=periode
    ).select_related('iku', 'pic_tim_kerja').order_by('iku__kode_indikator')

    if request.user.role == 'OPERATOR':
        qs = qs.filter(pic_tim_kerja=request.user)

    return render(request, 'iku_list.html', {
        'periode': periode,
        'periodes': periodes,
        'entries': qs,
    })


@login_required
def operator_workspace_view(request, iku_id):
    config = get_active_config()
    periodes = PeriodeKertasKerja.objects.all().order_by('-tahun', '-triwulan')
    
    iku = get_object_or_404(MasterIKU, id=iku_id)
    periode = iku.periode  # Selalu gunakan periode dari IKU yang dipilih
    
    target_entry, _ = FRAEntry.objects.get_or_create(iku=iku)

    # Fetch entries for sidebar list
    qs = FRAEntry.objects.filter(
        iku__periode=periode
    ).select_related('iku', 'pic_tim_kerja').order_by('iku__kode_indikator')

    if request.user.role == 'OPERATOR':
        qs = qs.filter(pic_tim_kerja=request.user)

    # Attach previous RTL to all entries in context
    attach_previous_rtl(qs, periode)

    total_iku = qs.count()
    done_iku = qs.filter(is_done=True).count()

    # Find the previous_rtl specifically for the target entry (for backward compatibility if needed)
    current_target_entry = None
    for entry in qs:
        if entry.id == target_entry.id:
            current_target_entry = entry
            break
    
    previous_rtl = current_target_entry.previous_rtl if current_target_entry else ""

    # Fetch RCO Peek Data for ALL IKUs based on the Triwulan
    tw = periode.triwulan
    tw_months = [(tw - 1) * 3 + 1, (tw - 1) * 3 + 2, (tw - 1) * 3 + 3]
    
    try:
        from .models import TahunKerja, MasterRO, RealisasiRO
        tahun_kerja = TahunKerja.objects.get(tahun=periode.tahun)
        iku_codes = [e.iku.kode_indikator for e in qs]
        all_ros = MasterRO.objects.filter(tahun=tahun_kerja).order_by('kode_ro')
        ro_ids = []
        for ro in all_ros:
            iku_list = [i.strip() for i in ro.kode_iku.split(',') if i.strip()]
            if any(k in iku_list for k in iku_codes):
                ro_ids.append(ro.id)

        realisasis = RealisasiRO.objects.filter(master_ro__id__in=ro_ids, bulan__in=tw_months)
        
        r_dict = {(r.master_ro_id, r.bulan): r.konten for r in realisasis}
        
        for entry in qs:
            entry.rco_peek_data = []
            ros_for_iku = [ro for ro in all_ros if entry.iku.kode_indikator in [i.strip() for i in ro.kode_iku.split(',') if i.strip()]]
            for ro in ros_for_iku:
                bulan_data = {m: r_dict.get((ro.id, m), "") for m in tw_months}
                entry.rco_peek_data.append({
                    'ro': ro,
                    'bulans': bulan_data
                })
    except Exception:
        for entry in qs:
            entry.rco_peek_data = []

    return render(request, 'iku_workspace.html', {
        'periode': periode,
        'periodes': periodes,
        'target_entry_id': str(target_entry.id),
        'entries': qs,
        'total': total_iku,
        'done': done_iku,
        'previous_rtl': previous_rtl,
        'tw_months': tw_months,
        'config_mapping_json': json.dumps(iku.cells),
    })

@csrf_exempt
@login_required
def update_entry_api(request, iku_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    iku = get_object_or_404(MasterIKU, id=iku_id)
    if iku.periode.is_locked:
        return JsonResponse({'error': 'Periode ini sudah dikunci.'}, status=403)

    entry = get_object_or_404(FRAEntry, iku=iku)

    try:
        data = json.loads(request.body)

        def to_float(val):
            if val is None or val == "":
                return None
            try:
                return float(str(val).replace(',', '.'))
            except ValueError:
                return None

        if 'realisasi' in data:
            entry.realisasi = str(data.get('realisasi', ''))
        if 'proksi_x_realisasi' in data:
            entry.proksi_x_realisasi = str(data.get('proksi_x_realisasi', ''))
        if 'proksi_y_realisasi' in data:
            entry.proksi_y_realisasi = str(data.get('proksi_y_realisasi', ''))
        if 'notulen' in data:
            entry.notulen = data['notulen']
        if 'kendala' in data:
            entry.kendala = data['kendala']
        if 'solusi' in data:
            entry.solusi = data['solusi']
        if 'rtl' in data:
            entry.rtl = data['rtl']
        if 'pic_rtl' in data:
            entry.pic_rtl = data['pic_rtl']
        if 'batas_waktu_rtl' in data:
            entry.batas_waktu_rtl = data['batas_waktu_rtl']
        if 'link_bukti_kinerja' in data:
            entry.link_bukti_kinerja = data['link_bukti_kinerja']
        if 'link_bukti_tl_sebelumnya' in data:
            entry.link_bukti_tl_sebelumnya = data['link_bukti_tl_sebelumnya']
        if 'link_solusi' in data:
            entry.link_solusi = data['link_solusi']
        if 'is_bukti_kinerja_done' in data:
            entry.is_bukti_kinerja_done = bool(data['is_bukti_kinerja_done'])
        if 'is_bukti_tl_done' in data:
            entry.is_bukti_tl_done = bool(data['is_bukti_tl_done'])
        if 'is_bukti_solusi_done' in data:
            entry.is_bukti_solusi_done = bool(data['is_bukti_solusi_done'])
        if 'is_done' in data:
            entry.is_done = bool(data['is_done'])

        entry.is_dirty = True
        if request.user.is_authenticated:
            entry.pic_tim_kerja = request.user

        entry.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ============================================================
# DRIVE EXPLORER
# ============================================================
@login_required
def drive_explorer_api(request):
    from .services.gdrive_service import fetch_folder_contents
    url = request.GET.get('url')
    if not url:
        return JsonResponse({'error': 'Missing URL parameter'}, status=400)
    try:
        items = fetch_folder_contents(url)
        return JsonResponse({'items': items})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

from .models import TahunKerja, MasterRO, RealisasiRO

# ============================================================
# RCO (Realisasi Capaian Output) - ADMIN
# ============================================================
@login_required
@role_required(['ADMIN'])
def manage_ro_view(request):
    tahuns = TahunKerja.objects.all().order_by('-tahun')
    tahun_id = request.GET.get('tahun_id')
    selected_tahun = None
    if tahuns.exists():
        selected_tahun = tahuns.get(id=tahun_id) if tahun_id else tahuns.first()

    ros = MasterRO.objects.filter(tahun=selected_tahun).order_by('kode_iku', 'kode_ro') if selected_tahun else []

    grouped_ros = {}
    if ros:
        for ro in ros:
            iku_list = [i.strip() for i in ro.kode_iku.split(',') if i.strip()]
            for iku_code in iku_list:
                if iku_code not in grouped_ros:
                    grouped_ros[iku_code] = []
                grouped_ros[iku_code].append(ro)
    
    # Fetch IKU names from MasterIKU
    iku_codes = list(grouped_ros.keys())
    iku_objs = MasterIKU.objects.filter(kode_indikator__in=iku_codes).values('kode_indikator', 'indikator')
    iku_map = {item['kode_indikator']: item['indikator'] for item in iku_objs}

    # Restructure for template ease
    final_grouped = {}
    for iku_code, ro_list in grouped_ros.items():
        final_grouped[iku_code] = {
            'name': iku_map.get(iku_code, 'Indikator tidak ditemukan'),
            'ros': ro_list
        }
    
    final_grouped_sorted = dict(sorted(final_grouped.items()))

    # Prepare JSON for Monaco Editor
    ros_list_for_json = []
    for ro in ros:
        ros_list_for_json.append({
            "kode_iku": ro.kode_iku,
            "kode_ro": ro.kode_ro,
            "nama_ro": ro.nama_ro,
            "kegiatan": ro.daftar_kegiatan
        })
    import json
    ros_json_str = json.dumps(ros_list_for_json, indent=4) if ros_list_for_json else "[]"

    return render(request, 'manage_ro.html', {
        'tahuns': tahuns,
        'selected_tahun': selected_tahun,
        'grouped_ros': final_grouped_sorted,
        'ros_json_str': ros_json_str
    })

@csrf_exempt
@login_required
@role_required(['ADMIN'])
def api_bulk_ro(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        tahun_id = data.get('tahun_id')
        json_data = data.get('json_data')
        
        tahun = TahunKerja.objects.get(id=tahun_id)
        parsed_data = json.loads(json_data)
        
        if not isinstance(parsed_data, list):
            raise ValueError("Format JSON harus berupa Array/List object.")
            
        updated_count = 0
        added_count = 0
        current_json_ro_codes = []
        
        for item in parsed_data:
            # Normalisasi: Buang spasi depan/belakang
            k_iku = str(item.get('kode_iku', '')).strip()
            k_ro = str(item.get('kode_ro', '')).strip() 
            n_ro = str(item.get('nama_ro', '')).strip()
            kegiatan = str(item.get('kegiatan', '')).strip()
            
            if not k_ro or not n_ro or not k_iku:
                continue
            
            current_json_ro_codes.append(k_ro)
                
            ro, created = MasterRO.objects.update_or_create(
                tahun=tahun, kode_ro=k_ro,
                defaults={
                    'kode_iku': k_iku,
                    'nama_ro': n_ro,
                    'daftar_kegiatan': kegiatan
                }
            )
            if created:
                added_count += 1
            else:
                updated_count += 1
        
        # FULL SYNC: Hapus RO di database yang tidak ada di dalam JSON (Source of Truth)
        # Hati-hati: Ini akan menghapus data RealisasiRO yang terkait jika RO dihapus
        deleted_count, _ = MasterRO.objects.filter(tahun=tahun).exclude(kode_ro__in=current_json_ro_codes).delete()
                
        return JsonResponse({
            'status': 'success', 
            'added': added_count, 
            'updated': updated_count,
            'deleted': deleted_count
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Format JSON tidak valid.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
@login_required
@role_required(['ADMIN'])
def api_manage_ro(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        action = data.get('action')
        
        if action == 'add_tahun':
            tahun = int(data.get('tahun'))
            TahunKerja.objects.get_or_create(tahun=tahun)
            return JsonResponse({'status': 'success'})
            
        elif action == 'set_active_tahun':
            TahunKerja.objects.update(is_active=False)
            TahunKerja.objects.filter(id=data.get('tahun_id')).update(is_active=True)
            return JsonResponse({'status': 'success'})
            
        elif action == 'delete_tahun':
            TahunKerja.objects.filter(id=data.get('tahun_id')).delete()
            return JsonResponse({'status': 'success'})
            
        elif action == 'save_ro':
            tahun = TahunKerja.objects.get(id=data.get('tahun_id'))
            ro_id = data.get('id')
            if ro_id:
                ro = MasterRO.objects.get(id=ro_id)
                ro.kode_iku = data.get('kode_iku')
                ro.kode_ro = data.get('kode_ro')
                ro.nama_ro = data.get('nama_ro')
                ro.daftar_kegiatan = data.get('daftar_kegiatan')
                ro.save()
            else:
                MasterRO.objects.create(
                    tahun=tahun,
                    kode_iku=data.get('kode_iku'),
                    kode_ro=data.get('kode_ro'),
                    nama_ro=data.get('nama_ro'),
                    daftar_kegiatan=data.get('daftar_kegiatan')
                )
            return JsonResponse({'status': 'success'})
            
        elif action == 'delete_ro':
            MasterRO.objects.filter(id=data.get('id')).delete()
            return JsonResponse({'status': 'success'})
            
        return JsonResponse({'error': 'Unknown action'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

# ============================================================
# RCO (Realisasi Capaian Output) - OPERATOR
# ============================================================
@login_required
def capaian_output_view(request):
    tahuns = TahunKerja.objects.all().order_by('-tahun')
    tahun_id = request.GET.get('tahun_id')
    selected_tahun = None
    if tahuns.exists():
        selected_tahun = tahuns.get(id=tahun_id) if tahun_id else tahuns.filter(is_active=True).first()
        if not selected_tahun:
            selected_tahun = tahuns.first()

    months = list(range(1, 13))
    grouped_matrix = {}
    
    if selected_tahun:
        if request.user.role == 'OPERATOR':
            entries = FRAEntry.objects.filter(pic_tim_kerja=request.user, iku__periode__tahun=selected_tahun.tahun)
            assigned_ikus = list(set(entries.values_list('iku__kode_indikator', flat=True)))
            ros = MasterRO.objects.filter(tahun=selected_tahun, kode_iku__in=assigned_ikus).order_by('kode_iku', 'kode_ro')
        else:
            ros = MasterRO.objects.filter(tahun=selected_tahun).order_by('kode_iku', 'kode_ro')

        ro_ids = ros.values_list('id', flat=True)
        realisasis = RealisasiRO.objects.filter(master_ro__id__in=ro_ids)
        r_dict = {(r.master_ro_id, r.bulan): r.konten for r in realisasis}

        for ro in ros:
            if ro.kode_iku not in grouped_matrix:
                grouped_matrix[ro.kode_iku] = []
                
            bulans = {}
            for m in months:
                bulans[m] = r_dict.get((ro.id, m), "")
                
            grouped_matrix[ro.kode_iku].append({
                'ro': ro,
                'bulans': bulans
            })

    # Fetch IKU names
    iku_codes = list(grouped_matrix.keys())
    iku_objs = MasterIKU.objects.filter(kode_indikator__in=iku_codes).values('kode_indikator', 'indikator')
    iku_map = {item['kode_indikator']: item['indikator'] for item in iku_objs}

    final_matrix = {}
    for iku_code, items in grouped_matrix.items():
        final_matrix[iku_code] = {
            'name': iku_map.get(iku_code, 'Indikator tidak ditemukan'),
            'items': items
        }
    
    final_matrix_sorted = dict(sorted(final_matrix.items()))

    return render(request, 'capaian_output.html', {
        'tahuns': tahuns,
        'selected_tahun': selected_tahun,
        'months': months,
        'grouped_matrix': final_matrix_sorted
    })

@csrf_exempt
@login_required
def api_save_rco(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        ro_id = data.get('ro_id')
        bulan = int(data.get('bulan'))
        konten = data.get('konten', '').strip()
        
        ro = MasterRO.objects.get(id=ro_id)
        if konten:
            r, _ = RealisasiRO.objects.update_or_create(master_ro=ro, bulan=bulan, defaults={'konten': konten})
        else:
            RealisasiRO.objects.filter(master_ro=ro, bulan=bulan).delete()
            
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

# ============================================================
# AUDIT KONSISTENSI (Admin Review)
# ============================================================
@csrf_exempt
@login_required
@role_required(['ADMIN'])
def api_audit_konsistensi(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        entry_id = data.get('entry_id')
        
        entry = FRAEntry.objects.select_related('iku', 'iku__periode').get(id=entry_id)
        periode = entry.iku.periode
        
        if not entry.link_bukti_kinerja:
            return JsonResponse({'error': 'Belum ada link folder GDrive untuk Bukti Kinerja.'}, status=400)
            
        tw = periode.triwulan
        tw_months = [(tw - 1) * 3 + 1, (tw - 1) * 3 + 2, (tw - 1) * 3 + 3]
        
        expected_files = []
        try:
            tahun_kerja = TahunKerja.objects.get(tahun=periode.tahun)
            all_ros = MasterRO.objects.filter(tahun=tahun_kerja)
            ros = [r for r in all_ros if entry.iku.kode_indikator in [i.strip() for i in r.kode_iku.split(',') if i.strip()]]
            for ro in ros:
                realisasis = RealisasiRO.objects.filter(master_ro=ro, bulan__in=tw_months)
                for r in realisasis:
                    if r.konten:
                        lines = r.konten.split('\n')
                        for line in lines:
                            line_clean = line.strip()
                            if line_clean:
                                expected_files.append({
                                    'ro_kode': ro.kode_ro,
                                    'ro_nama': ro.nama_ro,
                                    'bulan': r.bulan,
                                    'expected_name': line_clean
                                })
        except TahunKerja.DoesNotExist:
            pass
            
        from .services.gdrive_service import fetch_folder_contents
        try:
            gdrive_files = fetch_folder_contents(entry.link_bukti_kinerja)
            actual_names = []
            for f in gdrive_files:
                name = f.get('name', '')
                name_no_ext = name.rsplit('.', 1)[0] if '.' in name else name
                actual_names.append({'original': name, 'no_ext': name_no_ext})
        except Exception as e:
            return JsonResponse({'error': f'Gagal mengambil data dari Google Drive: {str(e)}'}, status=400)
            
        results = []
        for expected in expected_files:
            expected_name = expected['expected_name']
            
            match_found = False
            matched_file = None
            
            for actual in actual_names:
                # Case-insensitive matching
                if expected_name.lower() == actual['original'].lower() or expected_name.lower() == actual['no_ext'].lower():
                    match_found = True
                    matched_file = actual['original']
                    break
                    
            results.append({
                'ro_kode': expected['ro_kode'],
                'bulan': expected['bulan'],
                'expected_name': expected_name,
                'is_match': match_found,
                'matched_file': matched_file
            })
            
        return JsonResponse({
            'status': 'success',
            'results': results,
            'gdrive_count': len(gdrive_files),
            'expected_count': len(expected_files),
        })
        
    except FRAEntry.DoesNotExist:
        return JsonResponse({'error': 'Entry IKU tidak ditemukan.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
