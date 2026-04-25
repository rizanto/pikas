import uuid
import re
from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('VIEWER', 'Viewer'),
        ('OPERATOR', 'Operator'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='OPERATOR')

    def __str__(self):
        return f"{self.username} ({self.role})"


def validate_pikas_json_schema(value):
    """Validate the config_mapping JSON structure for a MasterIKU."""
    if not isinstance(value, dict):
        raise ValidationError("config_mapping must be a JSON object.")

    if "proxy_config" not in value:
        raise ValidationError("Missing 'proxy_config' in config_mapping.")

    proxy = value["proxy_config"]
    if not isinstance(proxy, dict):
        raise ValidationError("'proxy_config' must be an object.")

    if "has_proxy" not in proxy or not isinstance(proxy["has_proxy"], bool):
        raise ValidationError("'has_proxy' boolean is required in proxy_config.")

    has_proxy = proxy["has_proxy"]
    if has_proxy:
        if "x_label" not in proxy or not isinstance(proxy["x_label"], str):
            raise ValidationError("'x_label' is required when has_proxy is true.")
        if "y_label" not in proxy or not isinstance(proxy["y_label"], str):
            raise ValidationError("'y_label' is required when has_proxy is true.")

    if "gsheet_mapping" not in value:
        raise ValidationError("Missing 'gsheet_mapping' in config_mapping.")

    gsheet = value["gsheet_mapping"]
    if not isinstance(gsheet, dict):
        raise ValidationError("'gsheet_mapping' must be an object.")

    if "cells" not in gsheet or not isinstance(gsheet["cells"], dict):
        raise ValidationError("'cells' object is required in gsheet_mapping.")

    cells = gsheet["cells"]
    valid_modes = ["PULL_ONLY", "TWO_WAY"]
    coord_pattern = re.compile(r"^[A-Z]{1,3}[0-9]+$")

    if has_proxy:
        if "proxy_x" not in cells or "proxy_y" not in cells:
            raise ValidationError("If has_proxy is true, 'proxy_x' and 'proxy_y' must exist in cells.")
    else:
        if "proxy_x" in cells or "proxy_y" in cells:
            raise ValidationError("If has_proxy is false, 'proxy_x' and 'proxy_y' must NOT exist in cells.")

    for cell_key, cell_val in cells.items():
        if not isinstance(cell_val, dict):
            raise ValidationError(f"Cell '{cell_key}' must be an object.")
        if "coord" not in cell_val or not isinstance(cell_val["coord"], str):
            raise ValidationError(f"Cell '{cell_key}' must have a 'coord' string.")

        if not coord_pattern.match(cell_val["coord"]):
            raise ValidationError(f"Cell '{cell_key}' coord '{cell_val['coord']}' does not match pattern ^[A-Z]{{1,3}}[0-9]+$")

        if "mode" not in cell_val or cell_val["mode"] not in valid_modes:
            raise ValidationError(f"Cell '{cell_key}' must have a 'mode' in {valid_modes}.")


# ============================================================
# PERIODE KERTAS KERJA — "Wadah" per triwulan
# ============================================================
class PeriodeKertasKerja(models.Model):
    """
    Merepresentasikan satu periode kertas kerja (misal: 2026 TW1).
    Setiap periode terhubung ke satu sheet di Google Spreadsheet.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tahun = models.IntegerField(validators=[MinValueValidator(2020)])
    triwulan = models.IntegerField(choices=[(1, 'TW I'), (2, 'TW II'), (3, 'TW III'), (4, 'TW IV')])
    sheet_name = models.CharField(
        max_length=100,
        help_text="Nama sheet di Google Spreadsheet, misal: 2026Q1"
    )
    config_json = models.JSONField(
        default=dict, blank=True,
        help_text="Master JSON config: daftar IKU beserta mapping koordinat cell GSheet."
    )
    is_locked = models.BooleanField(
        default=False,
        help_text="Jika True, Operator tidak bisa submit/edit FRA."
    )
    is_configured = models.BooleanField(
        default=False,
        help_text="True jika config_json sudah diisi dan PULL sudah dilakukan."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tahun', 'triwulan')
        ordering = ['-tahun', '-triwulan']
        verbose_name_plural = "Periode Kertas Kerja"

    def __str__(self):
        return f"{self.tahun} TW{self.triwulan} ({self.sheet_name})"

    @property
    def label(self):
        return f"{self.tahun} TW{self.triwulan}"

    @property
    def iku_count(self):
        return self.ikus.count()


# ============================================================
# APP CONFIG — Singleton, menyimpan GSheet ID & periode aktif
# ============================================================
class AppConfig(models.Model):
    """
    Singleton. Menyimpan satu GSheet ID untuk seluruh sistem,
    dan pointer ke periode mana yang sedang aktif.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gsheet_id = models.CharField(
        max_length=255,
        help_text="ID unik dari URL Google Spreadsheet (satu untuk semua periode)."
    )
    active_periode = models.ForeignKey(
        PeriodeKertasKerja,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        help_text="Periode yang sedang aktif untuk Dashboard & Operator."
    )
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Enforce Singleton Pattern."""
        if AppConfig.objects.exclude(pk=self.pk).exists():
            raise ValidationError("Hanya boleh ada satu konfigurasi aktif.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"AppConfig (GSheet: {self.gsheet_id[:20]}...)"

    class Meta:
        verbose_name_plural = "App Config"


# ============================================================
# MASTER IKU — Blueprint IKU per periode
# ============================================================
class MasterIKU(models.Model):
    """
    Blueprint IKU per periode. Dibuat otomatis dari config_json + PULL.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    periode = models.ForeignKey(
        PeriodeKertasKerja,
        related_name='ikus',
        on_delete=models.CASCADE
    )
    kode_indikator = models.CharField(max_length=50, db_index=True)
    tujuan = models.TextField(blank=True, default='')
    kode_tujuan = models.CharField(max_length=50, blank=True, default='')
    sasaran = models.TextField(blank=True, default='')
    kode_sasaran = models.CharField(max_length=50, blank=True, default='')
    indikator = models.TextField(blank=True, default='', help_text='Nama indikator IKU')
    jenis_iku = models.CharField(max_length=20, default='IKU', choices=[('IKU', 'IKU Utama'), ('PROKSI', 'Proksi')])
    jenis_periode = models.CharField(max_length=20, default='TRIWULANAN', choices=[
        ('TAHUNAN', 'Tahunan'),
        ('TRIWULANAN', 'Triwulanan'),
    ])
    jenis_persen = models.BooleanField(default=True, help_text='True jika satuan persen')
    satuan = models.CharField(max_length=50, blank=True, default='')
    has_proxy = models.BooleanField(default=False)
    proxy_x_label = models.CharField(max_length=255, blank=True, default='')
    proxy_y_label = models.CharField(max_length=255, blank=True, default='')

    # Cell mapping untuk IKU ini (disalin dari config_json saat save)
    cells = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"[{self.kode_indikator}] {self.indikator} — {self.periode.label}"

    class Meta:
        unique_together = ('periode', 'kode_indikator')
        ordering = ['kode_indikator']
        verbose_name_plural = "Master IKU"


# ============================================================
# FRA ENTRY — Data isian per IKU (1 IKU = 1 Entry)
# ============================================================
class FRAEntry(models.Model):
    """
    Data isian untuk setiap IKU. Karena MasterIKU sudah terikat
    ke PeriodeKertasKerja, FRAEntry tidak perlu lagi menyimpan
    tahun/triwulan secara terpisah.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    iku = models.OneToOneField(MasterIKU, related_name='entry', on_delete=models.CASCADE)

    # Semua data yang di-PULL dari GSheet disimpan di sini
    pulled_data = models.JSONField(
        default=dict, blank=True,
        help_text="Semua nilai PULL_ONLY dari GSheet (target, capaian, alokasi, PKO, dll)"
    )

    # TWO_WAY Fields (Operator bisa edit, bisa di-PUSH balik)
    kendala = models.TextField(blank=True, default='')
    solusi = models.TextField(blank=True, default='')
    rtl = models.TextField(blank=True, default='')
    pic_rtl = models.CharField(max_length=255, blank=True, default='')
    batas_waktu_rtl = models.CharField(max_length=255, blank=True, default='')
    link_bukti_kinerja = models.URLField(max_length=500, blank=True, default='')
    link_bukti_tl_sebelumnya = models.URLField(max_length=500, blank=True, default='')
    link_solusi = models.URLField(max_length=500, blank=True, default='')

    # Realisasi (TWO_WAY per TW aktif)
    realisasi = models.CharField(max_length=100, blank=True, default='')
    proksi_x_realisasi = models.CharField(max_length=100, blank=True, default='')
    proksi_y_realisasi = models.CharField(max_length=100, blank=True, default='')

    # State & Audit Flags
    is_done = models.BooleanField(default=False)
    is_dirty = models.BooleanField(
        default=False,
        help_text="TRUE jika sudah di-save operator. Memblokir PULL overwrite."
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    pic_tim_kerja = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name_plural = "FRA Entries"

    def __str__(self):
        return f"{self.iku.kode_indikator} — {self.iku.periode.label}"
