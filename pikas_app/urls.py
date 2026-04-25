from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('', views.dashboard_view, name='dashboard'),

    # Pengguna
    path('pengguna/', views.pengguna_view, name='pengguna'),
    path('api/pengguna/', views.api_manage_user, name='api_manage_user'),

    # Kertas Kerja
    path('kertas-kerja/', views.kertas_kerja_view, name='kertas_kerja'),
    path('kertas-kerja/<uuid:periode_id>/', views.periode_config_view, name='periode_config'),
    path('kertas-kerja/<uuid:periode_id>/view/', views.periode_review_view, name='periode_review'),
    path('api/kertas-kerja/', views.api_kertas_kerja, name='api_kertas_kerja'),
    path('api/kertas-kerja/<uuid:periode_id>/', views.api_periode_config, name='api_periode_config'),

    # IKU Workspace (Operator)
    path('iku/', views.iku_list_view, name='iku_list'),
    path('entry/<uuid:iku_id>/', views.operator_workspace_view, name='entry_form'),
    path('api/entry/<uuid:iku_id>/', views.update_entry_api, name='api_update_entry'),

    # Drive Explorer
    path('api/drive-explorer/', views.drive_explorer_api, name='api_drive_explorer'),
]
