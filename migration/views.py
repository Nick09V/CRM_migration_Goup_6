"""Vistas web con soporte HTMX para autenticación y dashboard."""

import logging
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.html import escape

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
	"""Router simple para dashboard según rol.

	En el futuro, si se agregan roles (agente/cliente/admin), aquí se puede
	bifurcar la plantilla o redirigir a diferentes dashboards.
	
	Args:
		request: HttpRequest autenticado (garantizado por @login_required)

	Returns:
		HttpResponse: Renderiza dashboard.html
	"""

	if request.user.is_superuser:
		return redirect("/admin/")

	return render(request, "migration/dashboard.html")
