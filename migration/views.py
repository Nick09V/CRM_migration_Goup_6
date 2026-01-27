"""Vistas web con soporte HTMX para autenticación y dashboard."""

import logging
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
from .models import Cita, Solicitante, Agente, Carpeta, Requisito

# Configuración de logging para auditoría
logger = logging.getLogger(__name__)


def home_view(request: HttpRequest) -> HttpResponse:
	"""Redirige al dashboard si está autenticado o al login si no."""
	if request.user.is_authenticated:
		return redirect("dashboard")
	return redirect("login")


def login_view(request: HttpRequest) -> HttpResponse:
	"""Maneja el login clásico y vía HTMX.

	Características:
	- Detecta si la petición viene de HTMX via header HX-Request
	- Si el login es exitoso, devuelve HX-Redirect al dashboard
	- Si falla, retorna fragmento HTML de error para inyectar en el slot
	- Valida entrada: no permite campos vacíos o con espacios solo
	- Loguea intentos fallidos para auditoría y seguridad
	
	Args:
		request: HttpRequest con GET o POST

	Returns:
		HttpResponse: Login template (GET), fragmento de error (POST HTMX fallido),
		o redirección (POST exitoso)
	"""

	if request.user.is_authenticated:
		return redirect("dashboard")

	if request.method == "POST":
		# Obtener y limpiar entrada del usuario (puede ser username o email)
		username = request.POST.get("username", "").strip()
		password = request.POST.get("password", "").strip()

		# Validación básica de entrada
		if not username or not password:
			error_msg = "Por favor completa todos los campos."
			logger.warning(f"Intento de login con campos vacíos desde {request.META.get('REMOTE_ADDR')}")
			
			if request.headers.get("HX-Request"):
				return render(
					request,
					"partials/login_error.html",
					{"error": error_msg},
					status=400
				)

			messages.error(request, error_msg)
			return render(request, "login.html")

		# Validar longitud mínima de username/email
		if len(username) < 3:
			error_msg = "Usuario o email debe tener al menos 3 caracteres."
			logger.warning(f"Intento de login con username muy corto: {escape(username)}")
			
			if request.headers.get("HX-Request"):
				return render(request, "partials/login_error.html", {"error": error_msg}, status=400)
			
			messages.error(request, error_msg)
			return render(request, "login.html")

		# Si viene un email, resolvemos el username asociado para permitir login por email
		lookup_username = username
		if "@" in username:
			user_match = User.objects.filter(email__iexact=username).first()
			if user_match:
				lookup_username = user_match.username
				logger.info(f"Login usando email para usuario: {escape(lookup_username)}")
			else:
				# Si no existe email, intentará fallar en authenticate igualmente
				logger.warning(f"Intento de login con email inexistente: {escape(username)}")

		# Intentar autenticar (soporta username o email resuelto)
		user = authenticate(request, username=lookup_username, password=password)

		if user:
			# Login exitoso
			login(request, user)
			logger.info(f"Login exitoso para usuario: {user.username} desde {request.META.get('REMOTE_ADDR')}")

			# Determinar destino según rol
			if user.is_superuser:
				target_url = reverse("dashboard")  # Usa reverse en lugar de URL hardcoded
			else:
				target_url = reverse("dashboard")

			# Si es petición HTMX, redirige via header
			if request.headers.get("HX-Request"):
				response = HttpResponse()
				response["HX-Redirect"] = target_url
				response.status_code = 200
				return response

			# Si es petición normal, redirige
			return redirect(target_url)

		# Credenciales inválidas
		error_msg = "Usuario o contraseña incorrectos."
		
		# Loguear intento fallido (sin exponer contraseña)
		logger.warning(
			f"Intento de login fallido para usuario: {escape(username)} "
			f"desde IP: {request.META.get('REMOTE_ADDR')} "
			f"User-Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}"
		)

		if request.headers.get("HX-Request"):
			return render(
				request,
				"partials/login_error.html",
				{"error": error_msg},
				status=200
			)

		messages.error(request, error_msg)
		return render(request, "login.html")

	return render(request, "login.html")


def logout_view(request: HttpRequest) -> HttpResponse:
	"""Cierra sesión y redirige al login.
	
	Nota: Solo acepta POST para protección contra CSRF.
	GET requests serán redirigidas al login.
	"""

	# Protección contra logout accidental vía GET
	if request.method != "POST":
		logger.warning(f"Intento de logout vía GET desde {request.META.get('REMOTE_ADDR')}")
		return redirect("login")

	usuario = request.user.username if request.user.is_authenticated else "Anonymous"
	logout(request)
	
	logger.info(f"Logout exitoso para usuario: {usuario} desde {request.META.get('REMOTE_ADDR')}")
	
	return redirect("login")


@login_required(login_url="login")
def dashboard_router(request: HttpRequest) -> HttpResponse:
	"""Router para dashboard según rol del usuario.
	
	- Si es Agente → dashboard_agente.html (si existe)
	- Si es Solicitante → dashboard_cliente.html con datos completos
	- Si es Superuser → /admin/
	
	Args:
		request: HttpRequest autenticado (garantizado por @login_required)

	Returns:
		HttpResponse: Renderiza el dashboard correspondiente
	"""

	# 1. Detectar si es un Agente
	if hasattr(request.user, 'agente'):
		# Por si en el futuro implementan dashboard de agente en esta rama
		return render(request, "migration/dashboard_agente.html")

	# 2. Si es Superuser
	if request.user.is_superuser:
		return redirect("/admin/")

	# 3. Si es Solicitante (Cliente)
	if hasattr(request.user, 'solicitante'):
		solicitante = request.user.solicitante
		
		# A. Obtener cita pendiente (próxima)
		cita_pendiente = Cita.objects.filter(
			solicitante=solicitante,
			estado=Cita.ESTADO_PENDIENTE
		).select_related('agente').order_by('inicio').first()

		# B. Obtener o crear carpeta del solicitante
		carpeta, created = Carpeta.objects.get_or_create(
			solicitante=solicitante,
			defaults={'tipo_visa': 'Turista'}  # Tipo por defecto, debería definirse en la lógica de negocio
		)

		# C. Obtener requisitos con sus documentos más recientes
		requisitos = Requisito.objects.filter(
			carpeta=carpeta
		).prefetch_related('documentos').order_by('nombre')

		# Preparar estructura de documentos para el template
		documentos = []
		for requisito in requisitos:
			# Obtener el documento más reciente de este requisito
			ultimo_doc = requisito.documentos.order_by('-version', '-subido_en').first()
			
			documentos.append({
				'id': requisito.id,
				'nombre': requisito.nombre,
				'version': ultimo_doc.version if ultimo_doc else 0,
				'estado': requisito.get_estado_display(),
				'estado_code': requisito.estado,
				'puede_subir': requisito.habilitado_para_subir and requisito.estado == Requisito.ESTADO_FALTANTE,
			})

		# D. KPIs
		total_realizadas = Cita.objects.filter(
			solicitante=solicitante,
			estado=Cita.ESTADO_REALIZADA
		).count()

		# E. Calcular progreso del expediente
		progreso = carpeta.calcular_progreso()

		# F. Preparar contexto completo
		context = {
			'cita': cita_pendiente,
			'solicitud': {
				'tipo_visa': carpeta.tipo_visa,
				'estado_expediente': carpeta.get_estado_display(),
				'progreso': progreso,
			},
			'documentos': documentos,
			'total_realizadas': total_realizadas,
		}

		return render(request, "migration/dashboard.html", context)

	# 4. Si no tiene perfil de solicitante ni agente
	logger.warning(f"Usuario {request.user.username} sin perfil de solicitante o agente")
	return render(request, "migration/dashboard.html", {
		'cita': None,
		'solicitud': {'tipo_visa': 'N/A', 'estado_expediente': 'Sin expediente', 'progreso': 0},
		'documentos': [],
		'total_realizadas': 0,
	})


# === Vistas HTMX para interacciones del dashboard ===

@login_required(login_url="login")
def confirmar_cancelacion(request: HttpRequest, cita_id: int) -> HttpResponse:
	"""Vista HTMX para mostrar modal de confirmación de cancelación de cita.
	
	Args:
		request: HttpRequest autenticado
		cita_id: ID de la cita a cancelar
	
	Returns:
		HttpResponse: Fragmento HTML con modal de confirmación
	"""
	try:
		cita = Cita.objects.get(id=cita_id, solicitante=request.user.solicitante)
		
		if not cita.puede_cancelar():
			return HttpResponse(
				'<div class="p-4 bg-red-50 text-red-700 rounded">No se puede cancelar esta cita (menos de 3 días de anticipación)</div>',
				status=400
			)
		
		# Devolver modal de confirmación
		html = f'''
		<div class="fixed inset-0 z-50 flex items-center justify-center p-4">
			<div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onclick="this.parentElement.remove()"></div>
			<div class="relative bg-white p-6 rounded-xl max-w-md w-full shadow-2xl">
				<h3 class="text-lg font-bold mb-4 text-gray-800">Confirmar Cancelación</h3>
				<p class="text-gray-600 mb-6">¿Estás seguro de que deseas cancelar tu cita del {cita.inicio.strftime("%d/%m/%Y a las %H:%M")}?</p>
				<div class="flex gap-3">
					<button class="flex-1 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors" 
							onclick="this.closest('.fixed').remove()">
						Cancelar
					</button>
					<button hx-post="/cita/cancelar/{cita_id}/" 
							hx-target="#appointments-section" 
							hx-swap="outerHTML"
							class="flex-1 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-semibold">
						Confirmar
					</button>
				</div>
			</div>
		</div>
		'''
		return HttpResponse(html)
		
	except Cita.DoesNotExist:
		return HttpResponse('<div class="p-4 bg-red-50 text-red-700 rounded">Cita no encontrada</div>', status=404)


@login_required(login_url="login")
def subir_doc(request: HttpRequest, requisito_id: int) -> HttpResponse:
	"""Vista HTMX para mostrar modal de subida de documento.
	
	Args:
		request: HttpRequest autenticado
		requisito_id: ID del requisito al que se subirá el documento
	
	Returns:
		HttpResponse: Fragmento HTML con modal de subida
	"""
	try:
		requisito = Requisito.objects.get(id=requisito_id, carpeta__solicitante=request.user.solicitante)
		
		html = f'''
		<div class="fixed inset-0 z-50 flex items-center justify-center p-4">
			<div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onclick="this.parentElement.remove()"></div>
			<div class="relative bg-white p-6 rounded-xl max-w-md w-full shadow-2xl">
				<h3 class="text-lg font-bold mb-4 text-gray-800">Subir Documento</h3>
				<p class="text-sm text-gray-600 mb-4">Requisito: <span class="font-semibold">{requisito.nombre}</span></p>
				
				<form hx-post="/documento/subir/{requisito_id}/" 
					  hx-encoding="multipart/form-data" 
					  hx-target="#docs-table" 
					  hx-swap="outerHTML"
					  class="space-y-4">
					<input type="hidden" name="csrfmiddlewaretoken" value="{request.COOKIES.get('csrftoken', '')}">
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-2">Seleccionar archivo</label>
						<input type="file" name="archivo" required 
							   class="w-full border border-gray-300 rounded-lg p-2 text-sm">
					</div>
					<div class="flex gap-3">
						<button type="button" class="flex-1 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors" 
								onclick="this.closest('.fixed').remove()">
							Cancelar
						</button>
						<button type="submit" 
								class="flex-1 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors font-semibold">
							Subir
						</button>
					</div>
				</form>
			</div>
		</div>
		'''
		return HttpResponse(html)
		
	except Requisito.DoesNotExist:
		return HttpResponse('<div class="p-4 bg-red-50 text-red-700 rounded">Requisito no encontrado</div>', status=404)


@login_required(login_url="login")
def mostrar_calendario(request: HttpRequest) -> HttpResponse:
	"""Vista HTMX para mostrar calendario de agendamiento de citas.
	
	Muestra los próximos 14 días disponibles (horario 8-12, lunes a sábado).
	
	Args:
		request: HttpRequest autenticado
	
	Returns:
		HttpResponse: Fragmento HTML con calendario
	"""
	from datetime import timedelta
	from migration.models import HORA_INICIO_ATENCION, HORA_FIN_ATENCION, DIAS_LABORALES
	
	solicitante = request.user.solicitante
	ahora_local = timezone.localtime(timezone.now())
	
	# Generar próximos 14 días laborales
	dias_disponibles = []
	fecha_actual = ahora_local.date()
	
	for i in range(1, 15):  # Próximos 14 días
		fecha = fecha_actual + timedelta(days=i)
		if fecha.weekday() in DIAS_LABORALES:  # Lunes a Sábado
			dias_disponibles.append(fecha)
	
	# HTML del calendario
	html = f'''
	<div class="fixed inset-0 z-50 flex items-center justify-center p-4">
		<div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onclick="this.parentElement.remove()"></div>
		<div class="relative bg-white dark:bg-background-dark p-6 rounded-xl max-w-2xl w-full shadow-2xl max-h-[90vh] overflow-y-auto">
			<div class="flex items-center justify-between mb-6">
				<h3 class="text-xl font-bold text-gray-800 dark:text-white flex items-center gap-2">
					<span class="material-symbols-outlined text-primary">calendar_month</span>
					Selecciona fecha y hora
				</h3>
				<button onclick="this.closest('.fixed').remove()" class="text-gray-400 hover:text-gray-600">
					<span class="material-symbols-outlined">close</span>
				</button>
			</div>
			
			<p class="text-sm text-gray-600 dark:text-gray-400 mb-6">Horario de atención: {HORA_INICIO_ATENCION}:00 - {HORA_FIN_ATENCION}:00 hrs | Días laborales</p>
			
			<div class="grid grid-cols-2 gap-4 mb-6">
	'''
	
	# Días del calendario
	for fecha in dias_disponibles:
		dia_semana = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'][fecha.weekday()]
		html += f'''
		<button onclick="document.querySelectorAll('.dia-btn').forEach(b => b.classList.remove('bg-primary', 'text-white')); this.classList.add('bg-primary', 'text-white'); document.getElementById('fecha-seleccionada').value = '{fecha.isoformat()}'; document.getElementById('horarios-container').classList.remove('hidden');"
				class="dia-btn p-4 border-2 border-gray-200 dark:border-gray-700 rounded-lg hover:border-primary transition-colors text-left">
			<p class="text-xs text-gray-500 dark:text-gray-400 uppercase">{dia_semana}</p>
			<p class="text-lg font-bold text-gray-900 dark:text-white">{fecha.day}</p>
			<p class="text-xs text-gray-500 dark:text-gray-400">{fecha.strftime("%B")}</p>
		</button>
		'''
	
	html += '''
			</div>
			
			<div id="horarios-container" class="hidden">
				<h4 class="font-bold text-gray-700 dark:text-gray-300 mb-3">Selecciona una hora:</h4>
				<div class="grid grid-cols-4 gap-2 mb-6">
	'''
	
	# Horarios disponibles
	for hora in range(HORA_INICIO_ATENCION, HORA_FIN_ATENCION):
		html += f'''
		<button onclick="document.querySelectorAll('.hora-btn').forEach(b => b.classList.remove('bg-primary', 'text-white')); this.classList.add('bg-primary', 'text-white'); document.getElementById('hora-seleccionada').value = '{hora}:00';"
				class="hora-btn px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-primary hover:text-white transition-colors font-medium text-sm">
			{hora}:00
		</button>
		'''
	
	html += f'''
				</div>
				
				<form hx-post="/cita/agendar/" 
					  hx-target="#cita-section" 
					  hx-swap="outerHTML"
					  class="flex gap-3">
					<input type="hidden" name="csrfmiddlewaretoken" value="{request.COOKIES.get('csrftoken', '')}">
					<input type="hidden" id="fecha-seleccionada" name="fecha" value="">
					<input type="hidden" id="hora-seleccionada" name="hora" value="">
					
					<button type="button" class="flex-1 py-3 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors font-semibold" 
							onclick="this.closest('.fixed').remove()">
						Cancelar
					</button>
					<button type="submit" 
							class="flex-1 py-3 bg-primary text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold flex items-center justify-center gap-2">
						<span class="material-symbols-outlined">check_circle</span>
						Confirmar Cita
					</button>
				</form>
			</div>
		</div>
	</div>
	'''
	
	return HttpResponse(html)


@login_required(login_url="login")
def agendar_cita(request: HttpRequest) -> HttpResponse:
	"""Vista HTMX para procesar el agendamiento de una cita.
	
	Crea una nueva cita respetando las reglas de negocio.
	Retorna la tarjeta de cita actualizada.
	
	Args:
		request: HttpRequest con POST data (fecha, hora)
	
	Returns:
		HttpResponse: Fragmento HTML con tarjeta de cita actualizada
	"""
	if request.method != 'POST':
		return HttpResponse('<div class="p-4 bg-red-50 text-red-700 rounded">Método no permitido</div>', status=405)
	
	try:
		solicitante = request.user.solicitante
		
		# Validar que no tenga cita pendiente
		if solicitante.tiene_cita_pendiente():
			return HttpResponse('''
				<div class="p-4 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 rounded-lg">
					<p class="font-bold mb-2">⚠️ Ya tienes una cita pendiente</p>
					<p class="text-sm">Debes cancelar o completar tu cita actual antes de agendar una nueva.</p>
				</div>
			''', status=400)
		
		# Obtener datos del formulario
		fecha_str = request.POST.get('fecha')
		hora_str = request.POST.get('hora')
		
		if not fecha_str or not hora_str:
			return HttpResponse('<div class="p-4 bg-red-50 text-red-700 rounded">Debes seleccionar fecha y hora</div>', status=400)
		
		# Parsear fecha y hora
		from datetime import datetime, time
		fecha = datetime.fromisoformat(fecha_str).date()
		hora = datetime.strptime(hora_str, '%H:%M').time()
		
		# Crear datetime combinado con timezone
		fecha_hora = timezone.make_aware(datetime.combine(fecha, hora))
		
		# Obtener un agente disponible
		agente = Agente.objects.filter(activo=True).first()
		if not agente:
			return HttpResponse('<div class="p-4 bg-red-50 text-red-700 rounded">No hay agentes disponibles</div>', status=500)
		
		# Verificar que el horario no esté ocupado
		cita_existente = Cita.objects.filter(agente=agente, inicio=fecha_hora).exists()
		if cita_existente:
			return HttpResponse('''
				<div class="p-4 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 rounded-lg">
					<p class="font-bold mb-2">⚠️ Horario no disponible</p>
					<p class="text-sm">Este horario ya está ocupado. Por favor selecciona otro.</p>
				</div>
			''', status=400)
		
		# Crear la cita (las validaciones se ejecutan en el modelo)
		cita = Cita.objects.create(
			solicitante=solicitante,
			agente=agente,
			inicio=fecha_hora,
			estado=Cita.ESTADO_PENDIENTE
		)
		
		logger.info(f"Cita agendada: {cita.id} para {solicitante.nombre} el {fecha_hora}")
		
		# Cerrar modal y actualizar tarjeta
		context = {'cita': cita}
		html = render(request, 'partials/cita_card.html', context).content.decode('utf-8')
		
		# Agregar script para cerrar el modal
		html += '<script>document.getElementById("calendar-modal").innerHTML = "";</script>'
		
		return HttpResponse(html)
		
	except ValidationError as e:
		error_msg = ' '.join(e.messages) if hasattr(e, 'messages') else str(e)
		return HttpResponse(f'''
			<div class="p-4 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 rounded-lg">
				<p class="font-bold mb-2">❌ Error al agendar</p>
				<p class="text-sm">{error_msg}</p>
			</div>
		''', status=400)
	except Exception as e:
		logger.error(f"Error al agendar cita: {e}")
		return HttpResponse('<div class="p-4 bg-red-50 text-red-700 rounded">Error al procesar la solicitud</div>', status=500)
