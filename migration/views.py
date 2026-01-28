"""Vistas web con soporte HTMX para autenticación y dashboard."""

import logging
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.template import context
from django.urls import reverse
from django.utils.html import escape
from .models import Cita, Solicitante, Agente, Requisito, Documento, Carpeta, TipoVisa, RequisitoVisa, TipoRequisito
from datetime import timedelta
from django.utils import timezone
from django.views.decorators.http import require_POST

# Configuración de logging para auditoría
logger = logging.getLogger(__name__)


def home_view(request: HttpRequest) -> HttpResponse:
    """Redirige al dashboard si está autenticado o al login si no."""
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


def login_view(request: HttpRequest) -> HttpResponse:
    # ... (Tu lógica de login está bien, la dejo resumida para no ocupar espacio) ...
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        if not username or not password:
            error_msg = "Por favor completa todos los campos."
            if request.headers.get("HX-Request"):
                return render(request, "partials/login_error.html", {"error": error_msg}, status=400)
            messages.error(request, error_msg)
            return render(request, "login.html")

        # Validación básica login...
        lookup_username = username
        if "@" in username:
            user_match = User.objects.filter(email__iexact=username).first()
            if user_match:
                lookup_username = user_match.username

        user = authenticate(request, username=lookup_username, password=password)

        if user:
            login(request, user)
            target_url = reverse("dashboard")
            if request.headers.get("HX-Request"):
                response = HttpResponse()
                response["HX-Redirect"] = target_url
                return response
            return redirect(target_url)

        error_msg = "Usuario o contraseña incorrectos."
        if request.headers.get("HX-Request"):
            return render(request, "partials/login_error.html", {"error": error_msg}, status=200)

        messages.error(request, error_msg)
        return render(request, "login.html")

    return render(request, "login.html")


def logout_view(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect("login")
    logout(request)
    return redirect("login")


@login_required(login_url="login")
def dashboard_router(request: HttpRequest) -> HttpResponse:
    """Router inteligente para dashboard según rol."""

    # ---------------------------------------------------------
    # 1. ROL AGENTE
    # ---------------------------------------------------------
    if hasattr(request.user, "agente"):
        agente = request.user.agente

        # A. Agenda Operativa (Calendario)
        hoy = timezone.now().date()
        inicio_calendario = hoy - timedelta(days=14)
        fin_calendario = hoy + timedelta(days=14)

        citas_rango = Cita.objects.filter(
            agente=agente, 
            inicio__date__range=[inicio_calendario, fin_calendario]
        ).order_by("inicio")

        citas_map = {}
        for c in citas_rango:
            fecha = c.inicio.date()
            if fecha not in citas_map:
                citas_map[fecha] = []
            citas_map[fecha].append(c.estado)

        dias_calendario = []
        for i in range(29):
            fecha_iter = inicio_calendario + timedelta(days=i)
            dias_calendario.append({
                "fecha": fecha_iter,
                "es_hoy": fecha_iter == hoy,
                "estados": citas_map.get(fecha_iter, []),
            })

        # --- CONTADORES Y LISTAS ---
        
        # 1. Total Pendientes (Número rojo arriba a la derecha)
        docs_pendientes = Requisito.objects.filter(documentos__estado='pendiente').distinct().count()
        
        # 2. Citas Próximas (Tarjetas Blancas)
        proximas_citas = (
            Cita.objects.filter(agente=agente, estado=Cita.ESTADO_PENDIENTE)
            .select_related("solicitante")
            .order_by("inicio")[:3]
        )

        # 3. [NUEVO] Clientes con Revisión Pendiente (Tarjetas Amarillas)
        # Esto es lo que te faltaba para que Juan Pérez aparezca en "Casos Activos"
        clientes_revision = Solicitante.objects.filter(
            requisitos__documentos__estado='pendiente', # Tiene docs pendientes
            citas__agente=agente # Es cliente de este agente
        ).distinct()[:3]

        context = {
            "agente": agente,
            "total_pendientes": docs_pendientes,
            "proximas_citas": proximas_citas,
            "clientes_revision": clientes_revision, # <--- ¡IMPORTANTE!
            "dias_calendario": dias_calendario,
            "mes_actual": hoy, 
        }
        return render(request, "migration/dashboard_agente.html", context)

    # ---------------------------------------------------------
    # 2. ROL SUPERUSUARIO
    # ---------------------------------------------------------
    if request.user.is_superuser:
        return redirect("/admin/")

    # ---------------------------------------------------------
    # 3. ROL CLIENTE
    # ---------------------------------------------------------
    if hasattr(request.user, 'solicitante'):
        solicitante = request.user.solicitante
        carpeta = getattr(solicitante, 'carpeta', None)
        requisitos = []
        pendientes_count = 0
        
        if carpeta:
            requisitos = solicitante.requisitos.all()
            pendientes_count = requisitos.filter(estado='faltante').count()

        context = {
            "solicitante": solicitante,
            "carpeta": carpeta,
            "requisitos": requisitos,
            "pendientes_count": pendientes_count,
            "es_cliente": True 
        }
        return render(request, "migration/dashboard.html", context)

    return redirect("login")


@login_required(login_url="login")
def cita_detalle(request: HttpRequest, cita_id: int) -> HttpResponse:
    """Vista para gestionar una cita específica."""

    # 1. Se busca la cita por ID --> Error 404 si no existe
    cita = get_object_or_404(Cita, id=cita_id)

    # 2. Se verifica que esa cita pertenece al agente logueado
    if hasattr(request.user, "agente") and cita.agente != request.user.agente:
        # Si un agente intenta ver la cita de otro, se manda al dashboard.
        return redirect("dashboard")

    # CORRECCIÓN AQUÍ: Sacamos esto del IF (Indentación a la izquierda)
    context = {"cita": cita}

    return render(request, "migration/cita_detail.html", context)


@login_required
def actualizar_tramite(request, cita_id):
    if request.method == "POST":
        cita = get_object_or_404(Cita, id=cita_id)
        tipo_codigo = request.POST.get('tipo_tramite') # ej: 'estudiantil'
        
        # 1. Actualizar el Solicitante
        cita.solicitante.tipo_visa = tipo_codigo
        cita.solicitante.save()
        
        # 2. Limpiar requisitos viejos 
        # Requisito.objects.filter(solicitante=cita.solicitante).delete() 

        # 3. Buscamos en la tabla pivote 'RequisitoVisa'
        requisitos_config = RequisitoVisa.objects.filter(
            tipo_visa__codigo=tipo_codigo,
            tipo_visa__activo=True
        ).select_related('tipo_requisito')
        
        count = 0
        for config in requisitos_config:
            # Se crea el requisito real para el cliente
            # Se usa get_or_create para no duplicar si ya existe
            Requisito.objects.get_or_create(
                solicitante=cita.solicitante,
                nombre=config.tipo_requisito.nombre, # Usamos el nombre del catálogo
                defaults={'estado': 'faltante'}
            )
            count += 1
            
        return HttpResponse(f"""
            <span class="text-xs font-bold text-emerald-600 animate-pulse">
                ¡Actualizado! {count} requisitos generados.
            </span>
            <script>setTimeout(() => location.reload(), 1000)</script>
        """)


# Catálogo para darle estilo a las opciones del buscador 
CATALOGO_METADATA = {
    "Antecedentes Penales": {"vigencia": "3 meses", "icon": "gavel"},
    "Pasaporte": {"vigencia": "6 meses min", "icon": "menu_book"},
    "Foto Carnet": {"vigencia": "Reciente", "icon": "face"},
    "Titulo Universitario": {"vigencia": "Indefinida", "icon": "school"},
    "Contrato de Trabajo": {"vigencia": "Vigente", "icon": "work"},
    "Estado de Cuenta": {"vigencia": "Último mes", "icon": "account_balance"},
    "Carta de Invitación": {"vigencia": "N/A", "icon": "mail"},
}

def _generar_html_sugerencia(nombre_req):
    """Ayuda a generar el HTML de un item de la lista izquierda."""
    meta = CATALOGO_METADATA.get(nombre_req, {"vigencia": "Consultar", "icon": "description"})
    return f"""
    <div class="w-full flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-primary hover:bg-blue-50/50 dark:hover:bg-primary/5 transition-all group text-left cursor-pointer mb-2">
        <div class="flex items-center gap-3">
            <div class="bg-slate-100 dark:bg-slate-800 p-2 rounded-lg text-slate-500 group-hover:text-primary transition-colors">
                <span class="material-symbols-outlined">{meta['icon']}</span>
            </div>
            <div>
                <p class="text-sm font-semibold text-slate-700 dark:text-slate-200">{nombre_req}</p>
                <p class="text-[10px] text-slate-400 uppercase font-bold">Vigencia: {meta['vigencia']}</p>
            </div>
        </div>
        <button 
            hx-post="/cita/agregar-requisito-manual/" 
            hx-vals='{{"nombre": "{nombre_req}"}}'
            hx-target="#lista-requisitos-derecha"
            class="bg-slate-100 dark:bg-slate-800 p-1.5 rounded-md text-slate-400 group-hover:bg-primary group-hover:text-white transition-all">
            <span class="material-symbols-outlined text-sm block">add</span>
        </button>
    </div>
    """

@login_required
def buscar_documentos(request, cita_id):
    """
    Busca documentos en el catálogo maestro (TipoRequisito).
    """
    query = request.GET.get('q', '').strip()
    cita = get_object_or_404(Cita, id=cita_id)
    
    # Si no escribe nada, no devolvemos nada (o podrías devolver sugerencias)
    if not query:
        return HttpResponse("")

    # 1. Obtenemos lo que el usuario YA tiene asignado para no repetirlo
    asignados = list(Requisito.objects.filter(solicitante=cita.solicitante).values_list('nombre', flat=True))
    
    # 2. Buscamos en el Catálogo (TipoRequisito)
    # Filtramos por nombre y excluimos los que ya tiene
    resultados = TipoRequisito.objects.filter(
        nombre__icontains=query, 
        activo=True
    ).exclude(nombre__in=asignados)[:5] # Máximo 5 resultados
    
    # 3. Construimos el HTML de respuesta
    html = ""
    for item in resultados:
        html += f"""
        <div class="flex items-center justify-between p-3 border-b border-slate-100 hover:bg-slate-50 transition-colors animate-fade-in-up">
            <div>
                <p class="text-sm font-bold text-slate-700">{item.nombre}</p>
                <p class="text-[10px] text-slate-400">{item.descripcion or 'Documento estándar'}</p>
            </div>
            <button 
                hx-post="/cita/agregar-req/{cita.id}/"
                hx-vals='{{"nombre": "{item.nombre}"}}'
                hx-target="#lista-requisitos"
                class="size-8 rounded-full bg-primary/10 text-primary hover:bg-primary hover:text-white flex items-center justify-center transition-all shadow-sm">
                <span class="material-symbols-outlined text-lg">add</span>
            </button>
        </div>
        """
    
    if not html:
        html = f"""
        <div class="p-4 text-center text-slate-400 italic text-xs">
            No se encontraron documentos con "{query}".
        </div>
        """
        
    return HttpResponse(html)

@login_required
def agregar_requisito_manual(request, cita_id):
    if request.method == "POST":
        cita = get_object_or_404(Cita, id=cita_id)
        nombre_req = request.POST.get('nombre')
        
        if nombre_req:
            # 1. Crear el requisito (Evita duplicados con get_or_create)
            Requisito.objects.get_or_create(
                solicitante=cita.solicitante,
                nombre=nombre_req,
                defaults={'estado': 'faltante', 'carga_habilitada': True}
            )
            
            # 2. Obtener la lista actualizada
            requisitos = cita.solicitante.requisitos.all().order_by('id')
            
            # 3. Generar el HTML exacto de la lista derecha
            html_response = ""
            for req in requisitos:
                # Lógica de colores según estado
                if req.estado == 'faltante':
                    badge = '<span class="text-[10px] font-bold px-2 py-1 rounded bg-rose-100 text-rose-600 uppercase">Faltante</span>'
                elif req.estado == 'pendiente':
                    badge = '<span class="text-[10px] font-bold px-2 py-1 rounded bg-amber-100 text-amber-600 uppercase">Revisión</span>'
                else:
                    badge = '<span class="text-[10px] font-bold px-2 py-1 rounded bg-emerald-100 text-emerald-600 uppercase">OK</span>'

                html_response += f"""
                <div class="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-lg mb-2 shadow-sm animate-fade-in">
                    <div class="flex items-center gap-3">
                        <div class="p-2 bg-slate-100 text-slate-500 rounded-lg">
                            <span class="material-symbols-outlined text-lg">description</span>
                        </div>
                        <span class="text-sm font-bold text-slate-700">{req.nombre}</span>
                    </div>
                    {badge}
                </div>
                """
            
            return HttpResponse(html_response)

    return HttpResponse(status=400)


@login_required
def eliminar_requisito(request, requisito_id):
    """Borra un requisito y devuelve la lista actualizada."""
    if request.method == "POST":
        # 1. Buscar y borrar
        requisito = get_object_or_404(Requisito, id=requisito_id)
        solicitante = requisito.solicitante # Se guarda la referencia
        requisito.delete()
        
        # 2. Reconstruir la lista HTML actualizada (Para que HTMX la pinte de nuevo)
        requisitos = solicitante.requisitos.all()
        
        if not requisitos.exists():
            return HttpResponse('<div class="p-10 text-center text-slate-400"><p class="text-sm italic">No hay requisitos asignados.</p></div>')

        html_response = '<ul class="divide-y divide-slate-100 dark:divide-slate-800">'
        
        for req in requisitos:
            # color según el estado
            color_class = "bg-emerald-100 text-emerald-600"
            if req.estado == 'faltante': color_class = "bg-rose-100 text-rose-600"
            elif req.estado == 'pendiente': color_class = "bg-amber-100 text-amber-600"

            html_response += f"""
            <li class="p-4 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors group">
                <div class="flex items-center gap-3">
                    <div class="bg-slate-100 dark:bg-slate-700 text-slate-500 p-2 rounded-lg">
                        <span class="material-symbols-outlined text-sm">description</span>
                    </div>
                    <div>
                        <p class="text-sm font-semibold text-slate-700 dark:text-slate-200">{req.nombre.title()}</p>
                        <span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded {color_class}">
                            {req.get_estado_display()}
                        </span>
                    </div>
                </div>
                
                <button 
                    hx-post="/cita/eliminar-req/{req.id}/"
                    hx-target="#lista-requisitos-derecha"
                    hx-confirm="¿Estás seguro de quitar este requisito?"
                    class="opacity-0 group-hover:opacity-100 p-2 text-slate-400 hover:text-rose-500 hover:bg-rose-50 rounded-full transition-all"
                    title="Eliminar requisito">
                    <span class="material-symbols-outlined text-lg">delete</span>
                </button>
            </li>
            """
        html_response += '</ul>'
        
        return HttpResponse(html_response)
    
    return HttpResponse(status=400)

# --- Agregar al final de views.py ---
from .models import Carpeta # Asegúrate de importar Carpeta arriba

@login_required
def enviar_solicitud(request, cita_id):
    if request.method == "POST":
        cita = get_object_or_404(Cita, id=cita_id)
        
        # 1. Habilitamos la carga para el cliente
        for req in cita.solicitante.requisitos.all():
            if req.estado == 'faltante':
                req.carga_habilitada = True
                req.save()
        
       
        cita.estado = Cita.ESTADO_EXITOSA 
        cita.save()
        
        # Redirigimos al dashboard con mensaje de éxito
        return redirect('dashboard') 

    return redirect('dashboard')

@login_required
def revision_documentos(request, solicitante_id):
    """Pantalla principal de auditoría (Muestra la grilla de tarjetas)."""
    solicitante = get_object_or_404(Solicitante, id=solicitante_id)
    requisitos = solicitante.requisitos.all()
    
    # Calcular Progreso (Basado en requisitos 'revisado')
    total = requisitos.count()
    aprobados = requisitos.filter(estado='revisado').count()
    progreso = int((aprobados / total) * 100) if total > 0 else 0
    
    context = {
        "solicitante": solicitante,
        "requisitos": requisitos,
        "progreso": progreso
    }
    return render(request, "migration/revision_docs.html", context)


@login_required
def procesar_documento(request, requisito_id, accion):
    """
    HTMX: Procesa la aprobación/rechazo y devuelve SOLO la tarjeta HTML actualizada.
    """
    if request.method == "POST":
        requisito = get_object_or_404(Requisito, id=requisito_id)
        documento = requisito.obtener_documento_actual()
        
        if not documento:
            return HttpResponse("Error: No hay documento", status=400)

        if accion == 'aprobar':
            # Estado Verde
            documento.estado = 'revisado'
            documento.save()
            requisito.estado = 'revisado'
            requisito.save()
            
        elif accion == 'rechazar':
            # Estado Rojo (y habilitamos carga nuevamente)
            documento.estado = 'faltante' # 
            documento.save()
            
            requisito.estado = 'faltante'
            requisito.habilitar_carga() 
            requisito.save()

        # Devuelve el partial (la tarjeta solita) actualizada
        return render(request, "partials/card_documento.html", {"req": requisito})

    return HttpResponse(status=400)

@login_required
def lista_documentos_pendientes(request):
    """
    Muestra todos los clientes que tienen documentos esperando revisión.
    """
    clientes_con_pendientes = Solicitante.objects.filter(
        requisitos__documentos__estado='pendiente'
    ).distinct()

    context = {
        "clientes": clientes_con_pendientes
    }
    return render(request, "migration/lista_pendientes.html", context)

@login_required
@require_POST
def aprobar_documento(request, requisito_id):
    requisito = get_object_or_404(Requisito, id=requisito_id)
    documento = requisito.obtener_documento_actual()
    
    if documento:
        # Usar texto directo 'revisado'
        documento.estado = 'revisado' 
        documento.save()
        requisito.estado = 'revisado'
        requisito.observaciones = "" 
        requisito.save()
    
    return render(request, "partials/card_documento.html", {"req": requisito})


@login_required
@require_POST
def rechazar_documento_modal(request):
    requisito_id = request.POST.get('requisito_id')
    motivo = request.POST.get('motivo')
    
    requisito = get_object_or_404(Requisito, id=requisito_id)
    
    # 1. Actualizar Documento
    documento = requisito.obtener_documento_actual()
    if documento:
        documento.estado = 'faltante'
        documento.save()
    
    # 2. Actualizar Requisito (Esto activa el color ROJO)
    requisito.estado = 'faltante'
    requisito.observaciones = motivo 
    requisito.habilitar_carga()
    requisito.save()

    # 3. CLAVE: Enviamos 'oob_swap=True' para que HTMX sepa reemplazar la tarjeta
    context = {"req": requisito, "oob_swap": True}
    return render(request, "partials/card_documento.html", context)

@login_required
def historial_versiones(request, requisito_id):
    """Obtiene todas las versiones de un requisito y renderiza el Drawer lateral."""
    requisito = get_object_or_404(Requisito, id=requisito_id)
    
    # Obtenemos todos los documentos ordenados por versión descendente (v3, v2, v1...)
    documentos = requisito.documentos.all().order_by('-version')
    
    context = {
        "req": requisito,
        "documentos": documentos
    }
    return render(request, "partials/drawer_historial.html", context)

@login_required
def lista_clientes(request):
    """
    Tabla maestra de clientes. 
    Muestra los casos para poder entrar a 'Asignar Requisitos'.
    """
    if hasattr(request.user, "agente"):
        # Traemos todas las citas de este agente, ordenadas por fecha
        # Usamos select_related para que sea rápido obtener datos del solicitante
        citas = Cita.objects.filter(agente=request.user.agente).select_related('solicitante').order_by('-inicio')
    else:
        citas = Cita.objects.all().select_related('solicitante').order_by('-inicio')
        
    return render(request, "migration/lista_clientes.html", {"citas": citas})

@login_required
def mis_citas(request):
    """Muestra todas las citas del agente."""
    if hasattr(request.user, "agente"):
        # Filtra las citas solo de este agente
        citas = Cita.objects.filter(agente=request.user.agente).order_by('inicio')
    else:
        # Si es admin, ve todas
        citas = Cita.objects.all().order_by('inicio')
        
    return render(request, "migration/mis_citas.html", {"citas": citas})