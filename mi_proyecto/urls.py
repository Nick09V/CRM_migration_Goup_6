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
from django.urls import path

from migration.views import (
    home_view, login_view, logout_view, dashboard_router,
    confirmar_cancelacion, subir_doc, mostrar_calendario, agendar_cita
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home_view, name="home"),
    path("login/", login_view, name="login"),
    # Logout solo acepta POST por seguridad (CSRF protection)
    path("logout/", logout_view, name="logout"),
    path("dashboard/", dashboard_router, name="dashboard"),
    
    # Vistas HTMX para dashboard de cliente
    path("cita/confirmar-cancelacion/<int:cita_id>/", confirmar_cancelacion, name="confirmar_cancelacion"),
    path("cita/calendario/", mostrar_calendario, name="mostrar_calendario"),
    path("cita/agendar/", agendar_cita, name="agendar_cita"),
    path("documento/subir/<int:requisito_id>/", subir_doc, name="subir_doc"),
]
