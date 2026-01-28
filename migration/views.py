"""
Vistas Django para la aplicación de migración.
Consume los servicios de dominio existentes en migration/services/.
"""
import mimetypes
from pathlib import Path

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.views.generic import ListView, DetailView, TemplateView
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden, FileResponse, Http404
from django.conf import settings

from .models import (
    Solicitante,
    Agente,
    Cita,
    Requisito,
    Documento,
    Carpeta,
    TipoVisa,
    CatalogoRequisito,
    TIPOS_VISA,
    ESTADO_DOCUMENTO_PENDIENTE,
    ESTADO_DOCUMENTO_REVISADO,
    ESTADO_DOCUMENTO_FALTANTE,
    ESTADO_CARPETA_APROBADO,
    ESTADO_CARPETA_CERRADA_ACEPTADA,
    ESTADO_CARPETA_CERRADA_RECHAZADA,
    REQUISITOS_POR_VISA,
)

from .forms import (
    SolicitanteForm,
    SolicitanteTipoVisaForm,
    AsignarRequisitosForm,
    AgendarCitaForm,
    ReprogramarCitaForm,
    SubirDocumentoForm,
    RevisionDocumentoForm,
    RegistrarResultadoVisaForm,
    BusquedaSolicitanteForm,
    LoginForm,
    RegistroSolicitanteForm,
    CrearAgenteForm,
    CrearTipoVisaForm,
    CrearRequisitoForm,
)

# Importar servicios de dominio existentes
from .services.scheduling import (
    SolicitudAgendamiento,
    agendar_cita,
    cancelar_cita,
    reprogramar_cita,
)
from .services.documentos import (
    subir_documento,
    obtener_o_crear_carpeta,
)
from .services.revision import (
    aprobar_documento,
    rechazar_documento,
    verificar_todos_documentos_revisados,
    marcar_carpeta_aprobada,
)
from .services.requisitos import (
    registrar_tipo_visa,
    asignar_requisitos,
    asignar_requisitos_dinamico,
    obtener_catalogo_requisitos,
    obtener_requisitos_sugeridos_por_visa,
    marcar_cita_exitosa,
)
from .services.administracion import (
    activar_agente,
    desactivar_agente,
    cambiar_estado_agente,
    crear_tipo_visa,
    crear_requisito_catalogo,
    obtener_tipos_visa_activos,
    obtener_tipos_visa_choices,
    obtener_todos_tipos_visa,
    obtener_catalogo_requisitos_activos,
    obtener_todos_requisitos_catalogo,
    inicializar_sistema,
)


# ==================== Utilidades de Roles ====================

def es_solicitante(user):
    """Verifica si el usuario es un solicitante."""
    if not user.is_authenticated:
        return False
    return hasattr(user, 'solicitante')


def es_agente(user):
    """Verifica si el usuario es un agente activo."""
    if not user.is_authenticated:
        return False
    if hasattr(user, 'agente'):
        return user.agente.activo
    return False


def es_agente_inactivo(user):
    """Verifica si el usuario es un agente pero está inactivo."""
    if not user.is_authenticated:
        return False
    if hasattr(user, 'agente'):
        return not user.agente.activo
    return False


def es_administrador(user):
    """Verifica si el usuario es administrador (superuser o staff)."""
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.is_staff


def obtener_rol_usuario(user):
    """Obtiene el rol del usuario autenticado."""
    if not user.is_authenticated:
        return None
    if user.is_superuser or user.is_staff:
        return 'administrador'
    if hasattr(user, 'agente') and user.agente.activo:
        return 'agente'
    if hasattr(user, 'solicitante'):
        return 'solicitante'
    return None


# ==================== Mixins de Autorización ====================

class SolicitanteMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin que solo permite acceso a solicitantes. Bloquea explícitamente a agentes."""
    login_url = 'migration:login'

    def test_func(self):
        user = self.request.user
        # Bloquear explícitamente a agentes (activos o inactivos)
        if hasattr(user, 'agente'):
            return False
        # Bloquear a administradores
        if es_administrador(user):
            return False
        # Solo permitir a solicitantes
        return es_solicitante(user)

    def handle_no_permission(self):
        user = self.request.user
        if user.is_authenticated:
            # Si es agente, redirigir a su panel
            if hasattr(user, 'agente'):
                messages.warning(self.request, 'Los agentes no tienen acceso al panel de solicitante.')
                if user.agente.activo:
                    return redirect('migration:agente_dashboard')
                else:
                    messages.error(self.request, 'Su cuenta de agente está desactivada.')
                    return redirect('migration:login')
            # Si es administrador, redirigir a su panel
            if es_administrador(user):
                messages.info(self.request, 'Redirigido al panel de administración.')
                return redirect('migration:admin_dashboard')
            # Otros casos
            messages.error(self.request, 'No tiene permiso para acceder a esta sección.')
            return redirect('migration:login')
        return super().handle_no_permission()


class AgenteMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin que solo permite acceso a agentes y administradores."""
    login_url = 'migration:login'

    def test_func(self):
        return es_agente(self.request.user) or es_administrador(self.request.user)

    def handle_no_permission(self):
        user = self.request.user
        if user.is_authenticated:
            # Si es solicitante, redirigir a su panel
            if es_solicitante(user):
                messages.warning(self.request, 'Los solicitantes no tienen acceso al panel de agente.')
                return redirect('migration:solicitante_panel')
            # Si es agente inactivo
            if es_agente_inactivo(user):
                messages.error(self.request, 'Su cuenta de agente está desactivada. Contacte al administrador.')
                return redirect('migration:login')
            # Otros casos
            messages.error(self.request, 'No tiene permiso para acceder al panel de agente.')
            return redirect('migration:login')
        return super().handle_no_permission()


class AdministradorMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin que solo permite acceso a administradores."""
    login_url = 'migration:login'

    def test_func(self):
        return es_administrador(self.request.user)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, 'Solo los administradores pueden acceder a esta sección.')
            return redirect('migration:login')
        return super().handle_no_permission()


# ==================== Vistas de Autenticación ====================

class LoginView(View):
    """Vista de inicio de sesión."""
    template_name = 'migration/auth/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return self._redirigir_segun_rol(request.user)
        form = LoginForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()

            # Verificar si es un agente inactivo
            if es_agente_inactivo(user):
                messages.error(
                    request,
                    'Su cuenta de agente está desactivada. Contacte al administrador.'
                )
                return render(request, self.template_name, {'form': form})

            login(request, user)
            messages.success(request, f'¡Bienvenido, {user.username}!')
            return self._redirigir_segun_rol(user)
        return render(request, self.template_name, {'form': form})

    def _redirigir_segun_rol(self, user):
        """Redirige al usuario según su rol."""
        if es_administrador(user):
            return redirect('migration:admin_dashboard')
        if es_agente(user):
            return redirect('migration:agente_dashboard')
        if es_solicitante(user):
            return redirect('migration:solicitante_panel')
        return redirect('migration:home')


class LogoutView(View):
    """Vista de cierre de sesión."""

    def get(self, request):
        logout(request)
        messages.info(request, 'Ha cerrado sesión exitosamente.')
        return redirect('migration:login')

    def post(self, request):
        logout(request)
        messages.info(request, 'Ha cerrado sesión exitosamente.')
        return redirect('migration:login')


class RegistroSolicitanteView(View):
    """Vista de registro para nuevos solicitantes."""
    template_name = 'migration/auth/registro.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('migration:home')
        form = RegistroSolicitanteForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = RegistroSolicitanteForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, '¡Registro exitoso! Bienvenido al sistema.')
            return redirect('migration:solicitante_panel')
        return render(request, self.template_name, {'form': form})


# ==================== Panel del Solicitante ====================

class SolicitantePanelView(SolicitanteMixin, TemplateView):
    """Panel principal del solicitante autenticado."""
    template_name = 'migration/solicitante/panel.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        solicitante = self.request.user.solicitante

        # Información del solicitante
        context['solicitante'] = solicitante

        # Cita pendiente
        context['cita_pendiente'] = solicitante.citas.filter(
            estado=Cita.ESTADO_PENDIENTE
        ).first()

        # Historial de citas
        context['historial_citas'] = solicitante.citas.exclude(
            estado=Cita.ESTADO_PENDIENTE
        ).order_by('-inicio')[:5]

        # Requisitos
        context['requisitos'] = solicitante.requisitos.all()

        # Carpeta
        try:
            context['carpeta'] = solicitante.carpeta
        except Carpeta.DoesNotExist:
            context['carpeta'] = None

        # Progreso de documentos
        requisitos = solicitante.requisitos.all()
        if requisitos.exists():
            total = requisitos.count()
            aprobados = requisitos.filter(estado=ESTADO_DOCUMENTO_REVISADO).count()
            context['progreso_documentos'] = int((aprobados / total) * 100)
        else:
            context['progreso_documentos'] = 0

        return context


# ==================== Panel del Administrador ====================

class AdminDashboardView(AdministradorMixin, TemplateView):
    """Panel de administración."""
    template_name = 'migration/admin/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Inicializar sistema si es necesario
        inicializar_sistema()

        # Estadísticas
        context['total_agentes'] = Agente.objects.count()
        context['agentes_activos'] = Agente.objects.filter(activo=True).count()
        context['agentes_inactivos'] = Agente.objects.filter(activo=False).count()
        context['total_solicitantes'] = Solicitante.objects.count()
        context['total_tipos_visa'] = TipoVisa.objects.filter(activo=True).count()
        context['total_requisitos'] = CatalogoRequisito.objects.filter(activo=True).count()

        # Listados
        context['agentes'] = Agente.objects.all()
        context['tipos_visa'] = TipoVisa.objects.all()
        context['requisitos_catalogo'] = CatalogoRequisito.objects.all()

        return context


class CrearAgenteView(AdministradorMixin, View):
    """Vista para crear nuevos agentes (solo admin)."""
    template_name = 'migration/admin/crear_agente.html'

    def get(self, request):
        form = CrearAgenteForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = CrearAgenteForm(request.POST)
        if form.is_valid():
            agente = form.save()
            messages.success(request, f'Agente "{agente.nombre}" creado exitosamente.')
            return redirect('migration:admin_dashboard')
        return render(request, self.template_name, {'form': form})


class CambiarEstadoAgenteView(AdministradorMixin, View):
    """Vista para activar/desactivar un agente."""

    def post(self, request, agente_pk):
        agente = get_object_or_404(Agente, pk=agente_pk)
        resultado = cambiar_estado_agente(agente)

        if resultado.exitoso:
            messages.success(request, resultado.mensaje)
        else:
            messages.warning(request, resultado.mensaje)

        return redirect('migration:admin_dashboard')


class CrearTipoVisaView(AdministradorMixin, View):
    """Vista para crear un nuevo tipo de visa."""
    template_name = 'migration/admin/crear_tipo_visa.html'

    def get(self, request):
        form = CrearTipoVisaForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = CrearTipoVisaForm(request.POST)
        if form.is_valid():
            try:
                resultado = crear_tipo_visa(
                    codigo=form.cleaned_data['codigo'],
                    nombre=form.cleaned_data['nombre'],
                    descripcion=form.cleaned_data.get('descripcion', '')
                )
                messages.success(request, resultado.mensaje)
                return redirect('migration:admin_dashboard')
            except ValidationError as e:
                messages.error(request, str(e.message))

        return render(request, self.template_name, {'form': form})


class CrearRequisitoView(AdministradorMixin, View):
    """Vista para crear un nuevo requisito en el catálogo."""
    template_name = 'migration/admin/crear_requisito.html'

    def get(self, request):
        form = CrearRequisitoForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = CrearRequisitoForm(request.POST)
        if form.is_valid():
            try:
                resultado = crear_requisito_catalogo(
                    nombre=form.cleaned_data['nombre'],
                    descripcion=form.cleaned_data.get('descripcion', '')
                )
                messages.success(request, resultado.mensaje)
                return redirect('migration:admin_dashboard')
            except ValidationError as e:
                messages.error(request, str(e.message))

        return render(request, self.template_name, {'form': form})


# ==================== Vistas Principales ====================

class HomeView(TemplateView):
    """Vista de la página principal."""
    template_name = 'migration/home.html'

    def get(self, request, *args, **kwargs):
        # Si el usuario está autenticado, redirigir según rol
        if request.user.is_authenticated:
            if es_administrador(request.user):
                return redirect('migration:admin_dashboard')
            if es_agente(request.user):
                return redirect('migration:agente_dashboard')
            if es_solicitante(request.user):
                return redirect('migration:solicitante_panel')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_solicitantes'] = Solicitante.objects.count()
        context['citas_pendientes'] = Cita.objects.filter(estado=Cita.ESTADO_PENDIENTE).count()
        context['documentos_pendientes'] = Documento.objects.filter(estado=ESTADO_DOCUMENTO_PENDIENTE).count()
        return context


# ==================== Vistas de Solicitantes ====================

class SolicitanteListView(AgenteMixin, ListView):
    """Lista todos los solicitantes."""
    model = Solicitante
    template_name = 'migration/solicitante/lista.html'
    context_object_name = 'solicitantes'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        busqueda = self.request.GET.get('busqueda', '')
        if busqueda:
            queryset = queryset.filter(
                Q(nombre__icontains=busqueda) | Q(cedula__icontains=busqueda)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_busqueda'] = BusquedaSolicitanteForm(self.request.GET)
        return context


class SolicitanteCreateView(AgenteMixin, View):
    """Crea un nuevo solicitante."""
    template_name = 'migration/solicitante/crear.html'

    def get(self, request):
        form = SolicitanteForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = SolicitanteForm(request.POST)
        if form.is_valid():
            solicitante = form.save()
            messages.success(request, f'Solicitante "{solicitante.nombre}" creado exitosamente.')
            return redirect('migration:solicitante_detalle', pk=solicitante.pk)
        return render(request, self.template_name, {'form': form})


class SolicitanteDetailView(AgenteMixin, DetailView):
    """Muestra el detalle de un solicitante (Dashboard)."""
    model = Solicitante
    template_name = 'migration/solicitante/detalle.html'
    context_object_name = 'solicitante'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        solicitante = self.object

        # Obtener cita pendiente si existe
        context['cita_pendiente'] = solicitante.citas.filter(
            estado=Cita.ESTADO_PENDIENTE
        ).first()

        # Obtener historial de citas
        context['historial_citas'] = solicitante.citas.exclude(
            estado=Cita.ESTADO_PENDIENTE
        ).order_by('-inicio')[:5]

        # Obtener requisitos y documentos
        context['requisitos'] = solicitante.requisitos.all()

        # Obtener carpeta si existe
        try:
            context['carpeta'] = solicitante.carpeta
        except Carpeta.DoesNotExist:
            context['carpeta'] = None

        # Calcular progreso de documentos
        requisitos = solicitante.requisitos.all()
        if requisitos.exists():
            total = requisitos.count()
            aprobados = requisitos.filter(estado=ESTADO_DOCUMENTO_REVISADO).count()
            context['progreso_documentos'] = int((aprobados / total) * 100)
        else:
            context['progreso_documentos'] = 0

        return context


class SolicitanteUpdateView(AgenteMixin, View):
    """Actualiza un solicitante existente."""
    template_name = 'migration/solicitante/editar.html'

    def get(self, request, pk):
        solicitante = get_object_or_404(Solicitante, pk=pk)
        form = SolicitanteForm(instance=solicitante)
        return render(request, self.template_name, {
            'form': form,
            'solicitante': solicitante
        })

    def post(self, request, pk):
        solicitante = get_object_or_404(Solicitante, pk=pk)
        form = SolicitanteForm(request.POST, instance=solicitante)
        if form.is_valid():
            form.save()
            messages.success(request, 'Solicitante actualizado exitosamente.')
            return redirect('migration:solicitante_detalle', pk=pk)
        return render(request, self.template_name, {
            'form': form,
            'solicitante': solicitante
        })


# ==================== Vistas de Citas ====================

class CitaAgendarView(LoginRequiredMixin, View):
    """Vista para agendar una nueva cita."""
    template_name = 'migration/cita/agendar.html'
    login_url = 'migration:login'

    def get(self, request, solicitante_pk):
        solicitante = get_object_or_404(Solicitante, pk=solicitante_pk)

        # Verificar si ya tiene cita pendiente
        if solicitante.tiene_cita_pendiente():
            messages.warning(
                request,
                'Ya tiene una cita pendiente. Debe cancelarla antes de agendar una nueva.'
            )
            return redirect('migration:solicitante_detalle', pk=solicitante_pk)

        form = AgendarCitaForm()
        return render(request, self.template_name, {
            'form': form,
            'solicitante': solicitante
        })

    def post(self, request, solicitante_pk):
        solicitante = get_object_or_404(Solicitante, pk=solicitante_pk)
        form = AgendarCitaForm(request.POST)

        if form.is_valid():
            try:
                inicio = form.get_inicio_datetime()
                solicitud = SolicitudAgendamiento(
                    solicitante=solicitante,
                    inicio=inicio
                )
                cita = agendar_cita(solicitud)
                messages.success(
                    request,
                    f'Cita agendada exitosamente para el {cita.inicio.strftime("%d/%m/%Y a las %H:%M")} '
                    f'con {cita.agente.nombre}.'
                )
                return redirect('migration:solicitante_detalle', pk=solicitante_pk)
            except ValidationError as e:
                messages.error(request, str(e.message))

        return render(request, self.template_name, {
            'form': form,
            'solicitante': solicitante
        })


class CitaCancelarView(LoginRequiredMixin, View):
    """Vista para cancelar una cita."""
    template_name = 'migration/cita/cancelar.html'
    login_url = 'migration:login'

    def get(self, request, cita_pk):
        cita = get_object_or_404(Cita, pk=cita_pk, estado=Cita.ESTADO_PENDIENTE)
        return render(request, self.template_name, {'cita': cita})

    def post(self, request, cita_pk):
        cita = get_object_or_404(Cita, pk=cita_pk, estado=Cita.ESTADO_PENDIENTE)
        solicitante_pk = cita.solicitante.pk

        try:
            resultado = cancelar_cita(cita)
            messages.success(request, resultado.mensaje)
        except ValidationError as e:
            messages.error(request, str(e.message))

        return redirect('migration:solicitante_detalle', pk=solicitante_pk)


class CitaReprogramarView(LoginRequiredMixin, View):
    """Vista para reprogramar una cita."""
    template_name = 'migration/cita/reprogramar.html'
    login_url = 'migration:login'

    def get(self, request, cita_pk):
        cita = get_object_or_404(Cita, pk=cita_pk, estado=Cita.ESTADO_PENDIENTE)
        form = ReprogramarCitaForm()
        return render(request, self.template_name, {
            'form': form,
            'cita': cita
        })

    def post(self, request, cita_pk):
        cita = get_object_or_404(Cita, pk=cita_pk, estado=Cita.ESTADO_PENDIENTE)
        form = ReprogramarCitaForm(request.POST)

        if form.is_valid():
            try:
                nuevo_inicio = form.get_nuevo_inicio_datetime()
                resultado = reprogramar_cita(cita, nuevo_inicio)
                messages.success(request, resultado.mensaje)
                return redirect('migration:solicitante_detalle', pk=cita.solicitante.pk)
            except ValidationError as e:
                messages.error(request, str(e.message))

        return render(request, self.template_name, {
            'form': form,
            'cita': cita
        })


# ==================== Vistas de Requisitos y Documentos ====================

class AsignarTipoVisaView(AgenteMixin, View):
    """Vista para asignar tipo de visa y requisitos de forma dinámica."""
    template_name = 'migration/requisitos/asignar_visa.html'

    def get(self, request, solicitante_pk):
        solicitante = get_object_or_404(Solicitante, pk=solicitante_pk)
        catalogo = obtener_catalogo_requisitos()

        # Si el catálogo está vacío, inicializarlo
        if not catalogo:
            from .models import CatalogoRequisito
            CatalogoRequisito.inicializar_catalogo()
            catalogo = obtener_catalogo_requisitos()

        # Inicializar tipos de visa si están vacíos
        tipos_visa_choices = obtener_tipos_visa_choices()
        if not tipos_visa_choices:
            from .models import TipoVisa
            TipoVisa.inicializar_tipos_default()
            tipos_visa_choices = obtener_tipos_visa_choices()

        form = AsignarRequisitosForm(
            initial={'tipo_visa': solicitante.tipo_visa} if solicitante.tipo_visa else {},
            catalogo_requisitos=catalogo
        )

        # Obtener requisitos sugeridos para cada tipo de visa (dinámico)
        requisitos_sugeridos = {
            codigo: obtener_requisitos_sugeridos_por_visa(codigo)
            for codigo, nombre in tipos_visa_choices
        }

        return render(request, self.template_name, {
            'form': form,
            'solicitante': solicitante,
            'catalogo_requisitos': catalogo,
            'requisitos_sugeridos': requisitos_sugeridos,
            'tipos_visa': tipos_visa_choices,
        })

    def post(self, request, solicitante_pk):
        solicitante = get_object_or_404(Solicitante, pk=solicitante_pk)
        catalogo = obtener_catalogo_requisitos()

        form = AsignarRequisitosForm(request.POST, catalogo_requisitos=catalogo)

        if form.is_valid():
            try:
                tipo_visa = form.cleaned_data['tipo_visa']
                requisitos_ids = form.cleaned_data['requisitos']

                resultado = asignar_requisitos_dinamico(
                    solicitante=solicitante,
                    tipo_visa=tipo_visa,
                    requisitos_seleccionados=requisitos_ids,
                    validar_fecha=False
                )

                messages.success(
                    request,
                    f'Tipo de visa asignado: {solicitante.get_tipo_visa_display()}. '
                    f'{resultado.mensaje}'
                )
                return redirect('migration:solicitante_detalle', pk=solicitante_pk)
            except ValidationError as e:
                messages.error(request, str(e.message))

        # Obtener tipos de visa dinámicos
        tipos_visa_choices = obtener_tipos_visa_choices()

        # Obtener requisitos sugeridos para cada tipo de visa
        requisitos_sugeridos = {
            codigo: obtener_requisitos_sugeridos_por_visa(codigo)
            for codigo, nombre in tipos_visa_choices
        }

        return render(request, self.template_name, {
            'form': form,
            'solicitante': solicitante,
            'catalogo_requisitos': catalogo,
            'requisitos_sugeridos': requisitos_sugeridos,
            'tipos_visa': tipos_visa_choices,
        })


class SubirDocumentoView(LoginRequiredMixin, View):
    """Vista para subir un documento."""
    template_name = 'migration/documentos/subir.html'
    login_url = 'migration:login'

    def get(self, request, requisito_pk):
        requisito = get_object_or_404(Requisito, pk=requisito_pk)
        form = SubirDocumentoForm()
        return render(request, self.template_name, {
            'form': form,
            'requisito': requisito
        })

    def post(self, request, requisito_pk):
        requisito = get_object_or_404(Requisito, pk=requisito_pk)
        form = SubirDocumentoForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                archivo = form.cleaned_data['archivo']
                resultado = subir_documento(
                    solicitante=requisito.solicitante,
                    nombre_requisito=requisito.nombre,
                    nombre_archivo=archivo.name,
                    contenido=archivo.read()
                )
                messages.success(request, resultado.mensaje)
                return redirect(
                    'migration:solicitante_detalle',
                    pk=requisito.solicitante.pk
                )
            except ValidationError as e:
                messages.error(request, str(e.message))

        return render(request, self.template_name, {
            'form': form,
            'requisito': requisito
        })


class GestionRequisitosView(LoginRequiredMixin, DetailView):
    """Vista para gestionar requisitos de un solicitante."""
    model = Solicitante
    template_name = 'migration/requisitos/gestion.html'
    context_object_name = 'solicitante'
    login_url = 'migration:login'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        solicitante = self.object

        requisitos_data = []
        for requisito in solicitante.requisitos.all():
            documento_actual = requisito.obtener_documento_actual()
            requisitos_data.append({
                'requisito': requisito,
                'documento': documento_actual,
                'puede_subir': requisito.puede_subir_nuevo_documento(),
            })

        context['requisitos_data'] = requisitos_data
        return context


# ==================== Vistas del Panel del Agente ====================

class AgenteDashboardView(AgenteMixin, TemplateView):
    """Dashboard principal del agente."""
    template_name = 'migration/agente/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Documentos pendientes de revisión
        context['documentos_pendientes'] = Documento.objects.filter(
            estado=ESTADO_DOCUMENTO_PENDIENTE
        ).select_related('requisito', 'requisito__solicitante').order_by('-creado_en')

        # Carpetas aprobadas pendientes de resultado de visa
        context['carpetas_aprobadas'] = Carpeta.objects.filter(
            estado=ESTADO_CARPETA_APROBADO
        ).select_related('solicitante')

        # Citas del día
        from django.utils import timezone
        hoy = timezone.localtime(timezone.now()).date()
        context['citas_hoy'] = Cita.objects.filter(
            inicio__date=hoy,
            estado=Cita.ESTADO_PENDIENTE
        ).select_related('solicitante', 'agente')

        # Estadísticas
        context['total_pendientes'] = context['documentos_pendientes'].count()
        context['total_carpetas_aprobadas'] = context['carpetas_aprobadas'].count()
        context['total_citas_hoy'] = context['citas_hoy'].count()

        return context


class RevisarDocumentoView(AgenteMixin, View):
    """Vista para revisar un documento (aprobar/rechazar)."""
    template_name = 'migration/agente/revisar_documento.html'

    def _detectar_tipo_archivo(self, nombre_archivo):
        """Detecta si el archivo es una imagen o PDF."""
        if not nombre_archivo:
            return False, False

        nombre_lower = nombre_archivo.lower()
        es_imagen = any(nombre_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'])
        es_pdf = nombre_lower.endswith('.pdf')

        return es_imagen, es_pdf

    def _verificar_archivo_existe(self, documento):
        """Verifica si el archivo físico existe."""
        if not documento.ruta_archivo:
            return False

        ruta_archivo = Path(documento.ruta_archivo)
        if not ruta_archivo.is_absolute():
            ruta_archivo = Path(settings.BASE_DIR) / documento.ruta_archivo

        return ruta_archivo.exists()

    def get(self, request, documento_pk):
        documento = get_object_or_404(
            Documento,
            pk=documento_pk,
            estado=ESTADO_DOCUMENTO_PENDIENTE
        )
        form = RevisionDocumentoForm()

        # Detectar tipo de archivo para mostrar visor adecuado
        es_imagen, es_pdf = self._detectar_tipo_archivo(documento.nombre_archivo)

        # Verificar si el archivo existe
        archivo_existe = self._verificar_archivo_existe(documento)

        return render(request, self.template_name, {
            'form': form,
            'documento': documento,
            'es_imagen': es_imagen,
            'es_pdf': es_pdf,
            'archivo_existe': archivo_existe,
        })

    def post(self, request, documento_pk):
        documento = get_object_or_404(
            Documento,
            pk=documento_pk,
            estado=ESTADO_DOCUMENTO_PENDIENTE
        )
        form = RevisionDocumentoForm(request.POST)

        # Detectar tipo de archivo para mostrar visor en caso de error
        es_imagen, es_pdf = self._detectar_tipo_archivo(documento.nombre_archivo)

        # Verificar si el archivo existe
        archivo_existe = self._verificar_archivo_existe(documento)

        if form.is_valid():
            try:
                accion = form.cleaned_data['accion']
                observaciones = form.cleaned_data.get('observaciones', '')

                if accion == 'aprobar':
                    resultado = aprobar_documento(documento)
                    messages.success(request, resultado.mensaje)

                    # Verificar si todos los documentos están revisados
                    if verificar_todos_documentos_revisados(documento):
                        carpeta = marcar_carpeta_aprobada(documento)
                        messages.info(
                            request,
                            f'¡Todos los documentos aprobados! La carpeta del solicitante '
                            f'ha sido marcada como aprobada.'
                        )
                else:
                    resultado = rechazar_documento(documento, observaciones)
                    messages.warning(request, resultado.mensaje)

                return redirect('migration:agente_dashboard')
            except ValidationError as e:
                messages.error(request, str(e.message))

        return render(request, self.template_name, {
            'form': form,
            'documento': documento,
            'es_imagen': es_imagen,
            'es_pdf': es_pdf,
            'archivo_existe': archivo_existe,
        })


class VerDocumentoView(AgenteMixin, View):
    """
    Vista para servir documentos de forma segura.
    Solo agentes y administradores pueden acceder a los documentos.
    """

    def get(self, request, documento_pk):
        documento = get_object_or_404(Documento, pk=documento_pk)

        # Verificar que el documento tenga una ruta de archivo
        if not documento.ruta_archivo:
            raise Http404("El documento no tiene un archivo asociado.")

        # Construir la ruta completa del archivo
        # La ruta_archivo puede ser relativa (ej: "Documentos/123/trabajo/ci/version_1/archivo.pdf")
        ruta_archivo = Path(documento.ruta_archivo)

        # Si la ruta no es absoluta, construirla desde BASE_DIR
        if not ruta_archivo.is_absolute():
            ruta_archivo = Path(settings.BASE_DIR) / documento.ruta_archivo

        # Verificar que el archivo exista
        if not ruta_archivo.exists():
            raise Http404(f"El archivo no fue encontrado en el sistema.")

        # Detectar el tipo MIME del archivo
        content_type, _ = mimetypes.guess_type(str(ruta_archivo))
        if content_type is None:
            content_type = 'application/octet-stream'

        # Abrir y servir el archivo
        try:
            archivo = open(ruta_archivo, 'rb')
            response = FileResponse(
                archivo,
                content_type=content_type,
                as_attachment=False  # False para mostrar en navegador
            )
            # Configurar headers para permitir visualización en iframe
            response['Content-Disposition'] = f'inline; filename="{documento.nombre_archivo}"'
            response['X-Frame-Options'] = 'SAMEORIGIN'  # Permitir iframe del mismo origen
            return response
        except IOError:
            raise Http404("No se pudo leer el archivo.")


class DescargarDocumentoView(AgenteMixin, View):
    """
    Vista para descargar documentos.
    Solo agentes y administradores pueden descargar documentos.
    """

    def get(self, request, documento_pk):
        documento = get_object_or_404(Documento, pk=documento_pk)

        # Verificar que el documento tenga una ruta de archivo
        if not documento.ruta_archivo:
            raise Http404("El documento no tiene un archivo asociado.")

        # Construir la ruta completa del archivo
        ruta_archivo = Path(settings.BASE_DIR) / documento.ruta_archivo

        # Verificar que el archivo exista
        if not ruta_archivo.exists():
            raise Http404("El archivo no fue encontrado en el sistema.")

        # Detectar el tipo MIME del archivo
        content_type, _ = mimetypes.guess_type(str(ruta_archivo))
        if content_type is None:
            content_type = 'application/octet-stream'

        # Abrir y servir el archivo para descarga
        try:
            archivo = open(ruta_archivo, 'rb')
            response = FileResponse(
                archivo,
                content_type=content_type,
                as_attachment=True  # True para forzar descarga
            )
            response['Content-Disposition'] = f'attachment; filename="{documento.nombre_archivo}"'
            return response
        except IOError:
            raise Http404("No se pudo leer el archivo.")


class RegistrarResultadoVisaView(AgenteMixin, View):
    """Vista para registrar el resultado de la visa."""
    template_name = 'migration/agente/registrar_resultado.html'

    def get(self, request, carpeta_pk):
        carpeta = get_object_or_404(
            Carpeta,
            pk=carpeta_pk,
            estado=ESTADO_CARPETA_APROBADO
        )
        form = RegistrarResultadoVisaForm()
        return render(request, self.template_name, {
            'form': form,
            'carpeta': carpeta
        })

    def post(self, request, carpeta_pk):
        carpeta = get_object_or_404(
            Carpeta,
            pk=carpeta_pk,
            estado=ESTADO_CARPETA_APROBADO
        )
        form = RegistrarResultadoVisaForm(request.POST)

        if form.is_valid():
            resultado = form.cleaned_data['resultado']
            motivo = form.cleaned_data.get('motivo_rechazo', '')

            if resultado == 'aprobada':
                carpeta.estado = ESTADO_CARPETA_CERRADA_ACEPTADA
                carpeta.save(update_fields=['estado'])
                messages.success(
                    request,
                    f'¡Felicidades! La visa de {carpeta.solicitante.nombre} ha sido aprobada. '
                    f'Carpeta cerrada exitosamente.'
                )
            else:
                carpeta.estado = ESTADO_CARPETA_CERRADA_RECHAZADA
                carpeta.observaciones = motivo
                carpeta.save(update_fields=['estado', 'observaciones'])
                messages.warning(
                    request,
                    f'La visa de {carpeta.solicitante.nombre} ha sido rechazada. '
                    f'Carpeta cerrada con observación.'
                )

            return redirect('migration:agente_dashboard')

        return render(request, self.template_name, {
            'form': form,
            'carpeta': carpeta
        })


class ListaCarpetasView(AgenteMixin, ListView):
    """Lista todas las carpetas con filtros."""
    model = Carpeta
    template_name = 'migration/agente/lista_carpetas.html'
    context_object_name = 'carpetas'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('solicitante')
        estado = self.request.GET.get('estado', '')
        if estado:
            queryset = queryset.filter(estado=estado)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['estado_filtro'] = self.request.GET.get('estado', '')
        return context


# ==================== Vistas de Citas para Agentes ====================

class ListaCitasView(AgenteMixin, ListView):
    """Lista todas las citas."""
    model = Cita
    template_name = 'migration/cita/lista.html'
    context_object_name = 'citas'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('solicitante', 'agente')
        estado = self.request.GET.get('estado', '')
        if estado:
            queryset = queryset.filter(estado=estado)
        return queryset.order_by('-inicio')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['estado_filtro'] = self.request.GET.get('estado', '')
        return context


class AtenderCitaView(AgenteMixin, View):
    """Vista para atender una cita (asignar requisitos)."""
    template_name = 'migration/cita/atender.html'

    def get(self, request, cita_pk):
        cita = get_object_or_404(Cita, pk=cita_pk, estado=Cita.ESTADO_PENDIENTE)
        solicitante = cita.solicitante

        # Verificar si ya tiene tipo de visa
        if not solicitante.tipo_visa:
            messages.warning(
                request,
                'El solicitante debe tener un tipo de visa asignado para atender la cita.'
            )
            return redirect('migration:asignar_tipo_visa', solicitante_pk=solicitante.pk)

        return render(request, self.template_name, {
            'cita': cita,
            'requisitos_visa': REQUISITOS_POR_VISA.get(solicitante.tipo_visa, [])
        })

    def post(self, request, cita_pk):
        cita = get_object_or_404(Cita, pk=cita_pk, estado=Cita.ESTADO_PENDIENTE)
        solicitante = cita.solicitante

        try:
            # Asignar requisitos
            resultado = asignar_requisitos(solicitante, validar_fecha=False)

            # Marcar cita como exitosa
            marcar_cita_exitosa(solicitante)

            # Crear carpeta si no existe
            obtener_o_crear_carpeta(solicitante)

            messages.success(
                request,
                f'Cita atendida exitosamente. {resultado.mensaje}'
            )
            return redirect('migration:agente_dashboard')
        except ValidationError as e:
            messages.error(request, str(e.message))
            return redirect('migration:atender_cita', cita_pk=cita_pk)
