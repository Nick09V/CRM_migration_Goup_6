"""
URL configuration for mi_proyecto project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from migration import views
from django.conf import settings
from django.conf.urls.static import static

from migration.views import home_view, login_view, logout_view, dashboard_router

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home_view, name="home"),
    path("login/", login_view, name="login"),
    # Logout solo acepta POST por seguridad (CSRF protection)
    path("logout/", logout_view, name="logout"),
    path("dashboard/", dashboard_router, name="dashboard"),
    path('cita/<int:cita_id>/', views.cita_detalle, name='cita_detalle'),
    path('cita/actualizar-tramite/<int:cita_id>/', views.actualizar_tramite, name='actualizar_tramite'),
    path('cita/buscar-docs/<int:cita_id>/', views.buscar_documentos, name='buscar_documentos'),
    path('cita/agregar-req/<int:cita_id>/', views.agregar_requisito_manual, name='agregar_requisito_manual'),
    path('cita/eliminar-req/<int:requisito_id>/', views.eliminar_requisito, name='eliminar_requisito'),
    path('cita/enviar-solicitud/<int:cita_id>/', views.enviar_solicitud, name='enviar_solicitud'),
    path('revision/<int:solicitante_id>/', views.revision_documentos, name='revision_documentos'),
    path('procesar-doc/<int:requisito_id>/<str:accion>/', views.procesar_documento, name='procesar_documento'),
    path('documentos-pendientes/', views.lista_documentos_pendientes, name='documentos_pendientes'),
    path('documento/aprobar/<int:requisito_id>/', views.aprobar_documento, name='aprobar_documento'),
    path('documento/rechazar-form/', views.rechazar_documento_modal, name='rechazar_documento_form'),
    path('documento/historial/<int:requisito_id>/', views.historial_versiones, name='historial_versiones'),
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('mis-citas/', views.mis_citas, name='mis_citas'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

