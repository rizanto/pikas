from .models import AppConfig


def pikas_context(request):
    """Inject active config into all templates."""
    config = AppConfig.objects.select_related('active_periode').first()
    return {
        'app_config': config,
        'active_config': config,
        'active_periode': config.active_periode if config else None,
    }
