"""
URLs de la aplicación de migración.
"""
from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'migration'

urlpatterns = [
    # Página principal - redirige al login
    path('', RedirectView.as_view(pattern_name='migration:login', permanent=False), name='home'),

    # Autenticación
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('registro/', views.RegistroSolicitanteView.as_view(), name='registro'),

    # Panel del Solicitante (autenticado)
    path('mi-panel/', views.SolicitantePanelView.as_view(), name='solicitante_panel'),

    # Panel de Administración
    path('admin-panel/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    path('admin-panel/crear-agente/', views.CrearAgenteView.as_view(), name='crear_agente'),
    path('admin-panel/agente/<int:agente_pk>/cambiar-estado/', views.CambiarEstadoAgenteView.as_view(), name='cambiar_estado_agente'),
    path('admin-panel/crear-tipo-visa/', views.CrearTipoVisaView.as_view(), name='crear_tipo_visa'),
    path('admin-panel/crear-requisito/', views.CrearRequisitoView.as_view(), name='crear_requisito'),

    # Solicitantes (solo agentes)
    path('solicitantes/', views.SolicitanteListView.as_view(), name='solicitante_lista'),
    path('solicitantes/nuevo/', views.SolicitanteCreateView.as_view(), name='solicitante_crear'),
    path('solicitantes/<int:pk>/', views.SolicitanteDetailView.as_view(), name='solicitante_detalle'),
    path('solicitantes/<int:pk>/editar/', views.SolicitanteUpdateView.as_view(), name='solicitante_editar'),

    # Citas
    path('solicitantes/<int:solicitante_pk>/agendar-cita/', views.CitaAgendarView.as_view(), name='agendar_cita'),
    path('citas/<int:cita_pk>/cancelar/', views.CitaCancelarView.as_view(), name='cancelar_cita'),
    path('citas/<int:cita_pk>/reprogramar/', views.CitaReprogramarView.as_view(), name='reprogramar_cita'),
    path('citas/', views.ListaCitasView.as_view(), name='lista_citas'),
    path('citas/<int:cita_pk>/atender/', views.AtenderCitaView.as_view(), name='atender_cita'),

    # Requisitos y Documentos
    path('solicitantes/<int:solicitante_pk>/asignar-visa/', views.AsignarTipoVisaView.as_view(), name='asignar_tipo_visa'),
    path('solicitantes/<int:pk>/requisitos/', views.GestionRequisitosView.as_view(), name='gestion_requisitos'),
    path('requisitos/<int:requisito_pk>/subir/', views.SubirDocumentoView.as_view(), name='subir_documento'),

    # Panel del Agente
    path('agente/', views.AgenteDashboardView.as_view(), name='agente_dashboard'),
    path('agente/documento/<int:documento_pk>/revisar/', views.RevisarDocumentoView.as_view(), name='revisar_documento'),
    path('agente/documento/<int:documento_pk>/ver/', views.VerDocumentoView.as_view(), name='ver_documento'),
    path('agente/documento/<int:documento_pk>/descargar/', views.DescargarDocumentoView.as_view(), name='descargar_documento'),
    path('agente/carpeta/<int:carpeta_pk>/resultado/', views.RegistrarResultadoVisaView.as_view(), name='registrar_resultado'),
    path('agente/carpetas/', views.ListaCarpetasView.as_view(), name='lista_carpetas'),
]
