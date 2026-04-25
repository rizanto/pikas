from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import AppConfig, PeriodeKertasKerja, MasterIKU, FRAEntry, CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Role Information', {'fields': ('role',)}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')


@admin.register(AppConfig)
class AppConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'gsheet_id', 'active_periode', 'updated_at')


@admin.register(PeriodeKertasKerja)
class PeriodeKertasKerjaAdmin(admin.ModelAdmin):
    list_display = ('tahun', 'triwulan', 'sheet_name', 'is_locked', 'is_configured')
    list_filter = ('tahun', 'is_locked', 'is_configured')


@admin.register(MasterIKU)
class MasterIKUAdmin(admin.ModelAdmin):
    list_display = ('kode_indikator', 'indikator', 'periode', 'jenis_iku', 'jenis_periode')
    search_fields = ('kode_indikator', 'indikator', 'tujuan', 'sasaran')
    list_filter = ('jenis_iku', 'periode')


@admin.register(FRAEntry)
class FRAEntryAdmin(admin.ModelAdmin):
    list_display = ('iku', 'is_done', 'is_dirty', 'last_synced_at')
    list_filter = ('is_done', 'is_dirty')
    search_fields = ('iku__kode_indikator', 'iku__indikator')
