from .models import AppConfig
from django.conf import settings


def pikas_context(request):
    """Inject active config into all templates."""
    try:
        config = AppConfig.objects.select_related('active_periode').first()
        active_periode = config.active_periode if config else None
    except Exception:
        config = None
        active_periode = None

    return {
        'app_config': config,
        'active_config': config,
        'active_periode': active_periode,
        'satker_name': getattr(settings, 'SATKER_NAME', 'BPS Indonesia'),
    }
