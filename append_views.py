import json

code = """
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

    return render(request, 'manage_ro.html', {
        'tahuns': tahuns,
        'selected_tahun': selected_tahun,
        'ros': ros
    })

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

    return render(request, 'capaian_output.html', {
        'tahuns': tahuns,
        'selected_tahun': selected_tahun,
        'months': months,
        'grouped_matrix': grouped_matrix
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
            ros = MasterRO.objects.filter(tahun=tahun_kerja, kode_iku=entry.iku.kode_indikator)
            for ro in ros:
                realisasis = RealisasiRO.objects.filter(master_ro=ro, bulan__in=tw_months)
                for r in realisasis:
                    if r.konten:
                        lines = r.konten.split('\\n')
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
                if expected_name == actual['original'] or expected_name == actual['no_ext']:
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
"""

with open('pikas_app/views.py', 'a', encoding='utf-8') as f:
    f.write(code)
