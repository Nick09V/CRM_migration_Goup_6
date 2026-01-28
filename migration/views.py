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
from .models import Cita, Solicitante, Agente, Requisito, REQUISITOS_POR_VISA, TIPO_VISA_ESTUDIANTIL
from datetime import timedelta
from django.utils import timezone

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

        # A. Lógica para el calendario (Agenda Operativa)
        hoy = timezone.now().date()
        inicio_calendario = hoy - timedelta(days=14)  # 2 semanas atrás
        fin_calendario = hoy + timedelta(days=14)     # 2 semanas adelante

        # Buscamos citas en el rango
        citas_rango = Cita.objects.filter(
            agente=agente, 
            inicio__date__range=[inicio_calendario, fin_calendario]
        ).order_by("inicio")

        # Mapeamos fechas a estados
        citas_map = {}
        for c in citas_rango:
            fecha = c.inicio.date()
            if fecha not in citas_map:
                citas_map[fecha] = []
            citas_map[fecha].append(c.estado)

        # lista de días para el template
        dias_calendario = []
        for i in range(29):
            fecha_iter = inicio_calendario + timedelta(days=i)
            dias_calendario.append({
                "fecha": fecha_iter,
                "es_hoy": fecha_iter == hoy,
                "estados": citas_map.get(fecha_iter, []),
            })

        # B. Consultas de Carga de Trabajo
        docs_pendientes = Requisito.objects.filter(documentos__estado='pendiente').distinct().count()
        
        # Citas próximas para "Casos Activos"
        proximas_citas = (
            Cita.objects.filter(agente=agente, estado=Cita.ESTADO_PENDIENTE)
            .select_related("solicitante")
            .order_by("inicio")[:3]
        )

        context = {
            "agente": agente,
            "total_pendientes": docs_pendientes, 
            "proximas_citas": proximas_citas,
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
    # 3. ROL CLIENTE (Solicitante)
    # ---------------------------------------------------------
	#la lógica para cargar los datos del cliente
    if hasattr(request.user, 'solicitante'):
        solicitante = request.user.solicitante
        
        # Buscamos su carpeta y requisitos
        carpeta = getattr(solicitante, 'carpeta', None)
        requisitos = []
        pendientes_count = 0
        
        if carpeta:
            requisitos = solicitante.requisitos.all()
            # Para el cliente, "pendiente" es lo que le FALTA subir (estado='faltante')
            pendientes_count = requisitos.filter(estado='faltante').count()

        context = {
            "solicitante": solicitante,
            "carpeta": carpeta,
            "requisitos": requisitos,
            "pendientes_count": pendientes_count,
            "es_cliente": True 
        }
        return render(request, "migration/dashboard.html", context)

    # Si el usuario no tiene rol definido (borde case)
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

# --- Pega esto al final de migration/views.py ---

@login_required(login_url="login")
def actualizar_tramite(request: HttpRequest, cita_id: int) -> HttpResponse:
    """Actualiza el tipo de visa del Solicitante y genera sus requisitos automáticamente."""
    
    if request.method == "POST":
        cita = get_object_or_404(Cita, id=cita_id)
        
        # 1. Verificar que la cita sea del agente
        if hasattr(request.user, 'agente') and cita.agente != request.user.agente:
            return HttpResponse("No autorizado", status=403)
            
        # 2. Obtener el valor del select
        nuevo_tipo_visa = request.POST.get('tipo_tramite')
        
        # 3. Actualizar al Solicitante
        solicitante = cita.solicitante
        solicitante.tipo_visa = nuevo_tipo_visa
        solicitante.save()

        # 4. Generar requisitos automáticos basados en el diccionario
        Requisito.objects.filter(solicitante=solicitante).delete()

        # Se busca la lista de requisitos para la visa seleccionada 
        lista_requisitos = REQUISITOS_POR_VISA.get(nuevo_tipo_visa, [])

        # Se crean los requisitos en la BD 
        for nombre_req in lista_requisitos:
            Requisito.objects.create(
                solicitante=solicitante,
                nombre=nombre_req,
                estado='faltante'
            )
        
        # 5. Feedback visual y carga de requisitos 
        return HttpResponse(f"""
            <span class="text-emerald-600 font-bold flex items-center gap-1 animate-pulse">
                <span class="material-symbols-outlined text-sm">check_circle</span>
                Requisitos Generados
            </span>
            
            <script>window.location.reload()</script>
        """)
            
    return HttpResponse(status=400)


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
    query = request.GET.get('q', '').lower()
    cita = get_object_or_404(Cita, id=cita_id)
    solicitante = cita.solicitante
    
    # Obtener documentos existentes
    existentes = list(Requisito.objects.filter(solicitante=solicitante).values_list('nombre', flat=True))
    
    # Armar lista maestra
    todos_posibles = set()
    for lista in REQUISITOS_POR_VISA.values():
        todos_posibles.update(lista)
    todos_posibles.update(CATALOGO_METADATA.keys())
    
    resultados_html = ""
    for item in todos_posibles:
        # Filtrar si coincide la búsqueda Y si NO lo tiene ya
        if query in item.lower() and item not in existentes:
            meta = CATALOGO_METADATA.get(item, {"vigencia": "Consultar", "icon": "description"})
            
            # Se genera el HTML aquí mismo para inyectar bien la URL
            resultados_html += f"""
            <div class="w-full flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-primary hover:bg-blue-50/50 dark:hover:bg-primary/5 transition-all group text-left cursor-pointer mb-2">
                <div class="flex items-center gap-3">
                    <div class="bg-slate-100 dark:bg-slate-800 p-2 rounded-lg text-slate-500 group-hover:text-primary transition-colors">
                        <span class="material-symbols-outlined">{meta['icon']}</span>
                    </div>
                    <div>
                        <p class="text-sm font-semibold text-slate-700 dark:text-slate-200">{item}</p>
                        <p class="text-[10px] text-slate-400 uppercase font-bold">Vigencia: {meta['vigencia']}</p>
                    </div>
                </div>
                <button 
                    hx-post="/cita/agregar-req/{cita_id}/" 
                    hx-vals='{{"nombre": "{item}"}}'
                    hx-target="#lista-requisitos-derecha"
                    class="bg-slate-100 dark:bg-slate-800 p-1.5 rounded-md text-slate-400 group-hover:bg-primary group-hover:text-white transition-all">
                    <span class="material-symbols-outlined text-sm block">add</span>
                </button>
            </div>
            """
            
    if not resultados_html:
        resultados_html = '<p class="text-xs text-slate-400 p-2 italic text-center">No hay sugerencias disponibles.</p>'
        
    return HttpResponse(resultados_html)


@login_required
def agregar_requisito_manual(request, cita_id):
    """Agrega el requisito y actualiza ambas listas (Izquierda y Derecha)."""
    if request.method == "POST":
        cita = get_object_or_404(Cita, id=cita_id)
        nombre = request.POST.get('nombre')
        
        # 1. Crear el requisito
        Requisito.objects.get_or_create(
            solicitante=cita.solicitante,
            nombre=nombre,
            defaults={'estado': 'faltante'}
        )
        
        # 2. Generar respuesta OOB (Out of Band): Actualiza DOS lugares a la vez
        
        # A. Se genera la lista derecha actualizada
        requisitos = cita.solicitante.requisitos.all()
        html_derecha = ""
        if requisitos:
            html_derecha = '<ul class="divide-y divide-slate-100 dark:divide-slate-800">'
            for req in requisitos:
                html_derecha += f"""
                <li class="p-4 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                    <div class="flex items-center gap-3">
                        <div class="bg-slate-100 dark:bg-slate-700 text-slate-500 p-2 rounded-lg">
                            <span class="material-symbols-outlined text-sm">description</span>
                        </div>
                        <div>
                            <p class="text-sm font-semibold text-slate-700 dark:text-slate-200">{req.nombre.title()}</p>
                            <span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-rose-100 text-rose-600">Pendiente</span>
                        </div>
                    </div>
                </li>
                """
            html_derecha += '</ul>'
            
        # B. Se retorna el HTML normal (para la derecha) + Un script para limpiar el buscador
        return HttpResponse(f"""
            {html_derecha}
            <script>htmx.trigger('#buscador-input', 'keyup')</script>
        """)

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
    """Finaliza la configuración, notifica al cliente y CIERRA la cita."""
    if request.method == "POST":
        cita = get_object_or_404(Cita, id=cita_id)
        solicitante = cita.solicitante

        # 1. Crear/Habilitar Carpeta
        carpeta, created = Carpeta.objects.get_or_create(
            solicitante=solicitante,
            defaults={'estado': 'pendiente'}
        )
        if not created and carpeta.estado == 'cerrada_aceptada':
             carpeta.estado = 'pendiente'
             carpeta.save()

        # Marcar la cita como REALIZADA
        cita.estado = Cita.ESTADO_REALIZADA
        cita.save()

        # 3. Mensaje de éxito
        messages.success(request, f"✅ Solicitud enviada y cita marcada como completada.")
        
        return redirect('dashboard')
    
    return HttpResponse(status=400)


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