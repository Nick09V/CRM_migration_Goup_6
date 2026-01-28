"""
Formularios Django para la aplicación de migración.
Maneja la validación de entrada de datos para el frontend.
"""
from django import forms
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from datetime import datetime, time, timedelta

from .models import (
    Solicitante,
    Agente,
    CatalogoRequisito,
    TipoVisa,
    TIPOS_VISA,
    HORA_INICIO_ATENCION,
    HORA_FIN_ATENCION,
    MAXIMO_SEMANAS_ANTICIPACION,
)


# ==================== Formularios de Autenticación ====================

class LoginForm(AuthenticationForm):
    """Formulario de inicio de sesión personalizado."""

    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Usuario',
            'autofocus': True,
        }),
        label='Usuario'
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Contraseña',
        }),
        label='Contraseña'
    )


class RegistroSolicitanteForm(UserCreationForm):
    """Formulario de registro para solicitantes (sin tipo de visa)."""

    nombre = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre completo',
        }),
        label='Nombre Completo'
    )

    cedula = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Número de cédula',
        }),
        label='Cédula de Identidad'
    )

    telefono = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Teléfono de contacto',
        }),
        label='Teléfono'
    )

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'correo@ejemplo.com',
        }),
        label='Correo Electrónico'
    )

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de usuario',
            }),
        }
        labels = {
            'username': 'Nombre de Usuario',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Contraseña',
        })
        self.fields['password2'].widget = forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmar contraseña',
        })
        self.fields['password1'].label = 'Contraseña'
        self.fields['password2'].label = 'Confirmar Contraseña'

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        if Solicitante.objects.filter(nombre=nombre).exists():
            raise forms.ValidationError('Ya existe un solicitante con este nombre.')
        return nombre

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get('email'):
            user.email = self.cleaned_data['email']
        if commit:
            user.save()
            # Crear el perfil de solicitante
            Solicitante.objects.create(
                usuario=user,
                nombre=self.cleaned_data['nombre'],
                cedula=self.cleaned_data.get('cedula', ''),
                telefono=self.cleaned_data.get('telefono', ''),
                email=self.cleaned_data.get('email', ''),
            )
        return user


class CrearAgenteForm(forms.Form):
    """Formulario para que el administrador cree agentes."""

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre de usuario',
        }),
        label='Nombre de Usuario'
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Contraseña',
        }),
        label='Contraseña'
    )

    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmar contraseña',
        }),
        label='Confirmar Contraseña'
    )

    nombre = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre completo del agente',
        }),
        label='Nombre del Agente'
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Este nombre de usuario ya está en uso.')
        return username

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        if Agente.objects.filter(nombre=nombre).exists():
            raise forms.ValidationError('Ya existe un agente con este nombre.')
        return nombre

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('Las contraseñas no coinciden.')

        return cleaned_data

    def save(self):
        # Crear el usuario
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            password=self.cleaned_data['password1'],
        )
        # Crear el perfil de agente
        agente = Agente.objects.create(
            usuario=user,
            nombre=self.cleaned_data['nombre'],
            activo=True,
        )
        return agente


class SolicitanteForm(forms.ModelForm):
    """Formulario para registro y edición de solicitantes."""

    tipo_visa = forms.ChoiceField(
        choices=[],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        label='Tipo de Visa'
    )

    class Meta:
        model = Solicitante
        fields = ['nombre', 'cedula', 'telefono', 'email', 'tipo_visa']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre completo',
                'required': True,
            }),
            'cedula': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de cédula',
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Teléfono de contacto',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'correo@ejemplo.com',
            }),
        }
        labels = {
            'nombre': 'Nombre Completo',
            'cedula': 'Cédula de Identidad',
            'telefono': 'Teléfono',
            'email': 'Correo Electrónico',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cargar tipos de visa dinámicamente desde la base de datos
        choices = [('', '--- Seleccione ---')]
        try:
            tipos_visa = TipoVisa.objects.filter(activo=True).values_list('codigo', 'nombre')
            choices.extend(list(tipos_visa))
        except Exception:
            choices.extend(list(TIPOS_VISA))
        self.fields['tipo_visa'].choices = choices


class SolicitanteTipoVisaForm(forms.Form):
    """Formulario para asignar tipo de visa a un solicitante."""

    tipo_visa = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        label='Tipo de Visa'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cargar tipos de visa dinámicamente desde la base de datos
        try:
            tipos_visa = TipoVisa.objects.filter(activo=True).values_list('codigo', 'nombre')
            if tipos_visa.exists():
                self.fields['tipo_visa'].choices = list(tipos_visa)
            else:
                self.fields['tipo_visa'].choices = TIPOS_VISA
        except Exception:
            self.fields['tipo_visa'].choices = TIPOS_VISA


class AsignarRequisitosForm(forms.Form):
    """
    Formulario para asignar tipo de visa y requisitos de forma dinámica.
    El agente selecciona el tipo de visa y los requisitos específicos para el solicitante.
    """

    tipo_visa = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'tipo_visa_select',
        }),
        label='Tipo de Visa'
    )

    requisitos = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input',
        }),
        label='Requisitos a Asignar',
        required=True,
    )

    def __init__(self, *args, **kwargs):
        catalogo_requisitos = kwargs.pop('catalogo_requisitos', None)
        super().__init__(*args, **kwargs)

        # Cargar tipos de visa dinámicamente desde la base de datos
        try:
            tipos_visa = TipoVisa.objects.filter(activo=True).values_list('codigo', 'nombre')
            if tipos_visa.exists():
                self.fields['tipo_visa'].choices = list(tipos_visa)
            else:
                self.fields['tipo_visa'].choices = TIPOS_VISA
        except Exception:
            self.fields['tipo_visa'].choices = TIPOS_VISA

        # Cargar requisitos dinámicamente desde la base de datos
        if catalogo_requisitos:
            self.fields['requisitos'].choices = [
                (req.id, req.nombre.title()) for req in catalogo_requisitos
            ]
        else:
            # Cargar desde la BD si no se pasó el catálogo
            try:
                requisitos = CatalogoRequisito.objects.filter(activo=True)
                self.fields['requisitos'].choices = [
                    (req.id, req.nombre.title()) for req in requisitos
                ]
            except Exception:
                pass

    def clean_requisitos(self):
        requisitos = self.cleaned_data.get('requisitos')
        if not requisitos:
            raise forms.ValidationError(
                'Debe seleccionar al menos un requisito para el solicitante.'
            )
        return [int(r) for r in requisitos]


def generar_opciones_horario():
    """Genera las opciones de horario disponibles (08:00 - 12:00)."""
    opciones = []
    for hora in range(HORA_INICIO_ATENCION, HORA_FIN_ATENCION):
        time_obj = time(hora, 0)
        label = f"{hora:02d}:00"
        opciones.append((time_obj.strftime('%H:%M'), label))
    return opciones


def generar_opciones_fecha():
    """Genera opciones de fecha para las próximas 2 semanas (excluyendo domingos)."""
    opciones = []
    hoy = timezone.localtime(timezone.now()).date()
    fecha_maxima = hoy + timedelta(weeks=MAXIMO_SEMANAS_ANTICIPACION)

    fecha_actual = hoy
    while fecha_actual <= fecha_maxima:
        # Excluir domingos (weekday() == 6)
        if fecha_actual.weekday() != 6:
            label = fecha_actual.strftime('%A %d/%m/%Y')
            opciones.append((fecha_actual.isoformat(), label))
        fecha_actual += timedelta(days=1)

    return opciones


def obtener_rango_fechas_validas():
    """Obtiene el rango de fechas válidas para agendar citas."""
    hoy = timezone.localtime(timezone.now()).date()
    fecha_minima = hoy
    fecha_maxima = hoy + timedelta(weeks=MAXIMO_SEMANAS_ANTICIPACION)
    return fecha_minima, fecha_maxima


class AgendarCitaForm(forms.Form):
    """Formulario para agendar una nueva cita."""

    fecha = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        }),
        label='Fecha de la Cita'
    )

    hora = forms.ChoiceField(
        choices=generar_opciones_horario(),
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        label='Hora de la Cita'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Establecer fechas mínima y máxima en el widget
        fecha_minima, fecha_maxima = obtener_rango_fechas_validas()
        self.fields['fecha'].widget.attrs['min'] = fecha_minima.isoformat()
        self.fields['fecha'].widget.attrs['max'] = fecha_maxima.isoformat()
        # Guardar para validaciones
        self.fecha_minima = fecha_minima
        self.fecha_maxima = fecha_maxima

    def clean_fecha(self):
        """Valida que la fecha esté en el rango permitido y no sea domingo."""
        fecha = self.cleaned_data.get('fecha')

        if fecha:
            # Verificar que no sea domingo
            if fecha.weekday() == 6:
                raise forms.ValidationError(
                    "No se pueden agendar citas en domingo. Por favor, seleccione otro día."
                )

            # Verificar rango de fechas
            if fecha < self.fecha_minima:
                raise forms.ValidationError(
                    "No se pueden agendar citas en fechas pasadas."
                )

            if fecha > self.fecha_maxima:
                raise forms.ValidationError(
                    f"Solo se pueden agendar citas con máximo {MAXIMO_SEMANAS_ANTICIPACION} semanas de anticipación."
                )

        return fecha

    def clean(self):
        """Valida que la fecha y hora seleccionadas no sean anteriores a la actual."""
        cleaned_data = super().clean()
        fecha = cleaned_data.get('fecha')
        hora_str = cleaned_data.get('hora')

        if fecha and hora_str:
            hora = datetime.strptime(hora_str, '%H:%M').time()
            dt_naive = datetime.combine(fecha, hora)
            inicio = timezone.make_aware(dt_naive)

            ahora = timezone.localtime(timezone.now())

            if inicio <= ahora:
                raise forms.ValidationError(
                    "No se puede agendar una cita en una fecha y hora anterior a la actual. "
                    "Por favor, seleccione un horario futuro."
                )

        return cleaned_data

    def get_inicio_datetime(self):
        """Convierte la fecha y hora seleccionadas a datetime con timezone."""
        fecha = self.cleaned_data['fecha']
        hora_str = self.cleaned_data['hora']

        hora = datetime.strptime(hora_str, '%H:%M').time()

        dt_naive = datetime.combine(fecha, hora)
        return timezone.make_aware(dt_naive)


class ReprogramarCitaForm(forms.Form):
    """Formulario para reprogramar una cita existente."""

    fecha = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        }),
        label='Nueva Fecha'
    )

    hora = forms.ChoiceField(
        choices=generar_opciones_horario(),
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        label='Nueva Hora'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Establecer fechas mínima y máxima en el widget
        fecha_minima, fecha_maxima = obtener_rango_fechas_validas()
        self.fields['fecha'].widget.attrs['min'] = fecha_minima.isoformat()
        self.fields['fecha'].widget.attrs['max'] = fecha_maxima.isoformat()
        # Guardar para validaciones
        self.fecha_minima = fecha_minima
        self.fecha_maxima = fecha_maxima

    def clean_fecha(self):
        """Valida que la fecha esté en el rango permitido y no sea domingo."""
        fecha = self.cleaned_data.get('fecha')

        if fecha:
            # Verificar que no sea domingo
            if fecha.weekday() == 6:
                raise forms.ValidationError(
                    "No se pueden reprogramar citas a domingo. Por favor, seleccione otro día."
                )

            # Verificar rango de fechas
            if fecha < self.fecha_minima:
                raise forms.ValidationError(
                    "No se pueden reprogramar citas a fechas pasadas."
                )

            if fecha > self.fecha_maxima:
                raise forms.ValidationError(
                    f"Solo se pueden reprogramar citas con máximo {MAXIMO_SEMANAS_ANTICIPACION} semanas de anticipación."
                )

        return fecha

    def clean(self):
        """Valida que la fecha y hora seleccionadas no sean anteriores a la actual."""
        cleaned_data = super().clean()
        fecha = cleaned_data.get('fecha')
        hora_str = cleaned_data.get('hora')

        if fecha and hora_str:
            hora = datetime.strptime(hora_str, '%H:%M').time()
            dt_naive = datetime.combine(fecha, hora)
            inicio = timezone.make_aware(dt_naive)

            ahora = timezone.localtime(timezone.now())

            if inicio <= ahora:
                raise forms.ValidationError(
                    "No se puede reprogramar una cita a una fecha y hora anterior a la actual. "
                    "Por favor, seleccione un horario futuro."
                )

        return cleaned_data

    def get_nuevo_inicio_datetime(self):
        """Convierte la fecha y hora seleccionadas a datetime con timezone."""
        fecha = self.cleaned_data['fecha']
        hora_str = self.cleaned_data['hora']

        hora = datetime.strptime(hora_str, '%H:%M').time()

        dt_naive = datetime.combine(fecha, hora)
        return timezone.make_aware(dt_naive)


class SubirDocumentoForm(forms.Form):
    """Formulario para subir un documento."""

    archivo = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx',
        }),
        label='Archivo del Documento'
    )

    def clean_archivo(self):
        archivo = self.cleaned_data.get('archivo')
        if archivo:
            # Validar tamaño máximo (10MB)
            if archivo.size > 10 * 1024 * 1024:
                raise forms.ValidationError(
                    'El archivo es demasiado grande. Máximo permitido: 10MB.'
                )

            # Validar extensión
            extensiones_permitidas = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
            nombre = archivo.name.lower()
            if not any(nombre.endswith(ext) for ext in extensiones_permitidas):
                raise forms.ValidationError(
                    f'Tipo de archivo no permitido. Extensiones permitidas: {", ".join(extensiones_permitidas)}'
                )

        return archivo


class RevisionDocumentoForm(forms.Form):
    """Formulario para revisar (aprobar/rechazar) un documento."""

    ACCIONES = [
        ('aprobar', 'Aprobar'),
        ('rechazar', 'Rechazar'),
    ]

    accion = forms.ChoiceField(
        choices=ACCIONES,
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input',
        }),
        label='Acción'
    )

    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Observaciones (requerido si se rechaza)',
        }),
        label='Observaciones'
    )

    def clean(self):
        cleaned_data = super().clean()
        accion = cleaned_data.get('accion')
        observaciones = cleaned_data.get('observaciones')

        if accion == 'rechazar' and not observaciones:
            raise forms.ValidationError(
                'Debe proporcionar observaciones al rechazar un documento.'
            )

        return cleaned_data


class RegistrarResultadoVisaForm(forms.Form):
    """Formulario para registrar el resultado de la visa del consulado."""

    RESULTADOS = [
        ('aprobada', 'Visa Aprobada'),
        ('rechazada', 'Visa Rechazada'),
    ]

    resultado = forms.ChoiceField(
        choices=RESULTADOS,
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input',
        }),
        label='Resultado de la Visa'
    )

    motivo_rechazo = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Motivo del rechazo (requerido si se rechaza)',
        }),
        label='Motivo del Rechazo'
    )

    def clean(self):
        cleaned_data = super().clean()
        resultado = cleaned_data.get('resultado')
        motivo = cleaned_data.get('motivo_rechazo')

        if resultado == 'rechazada' and not motivo:
            raise forms.ValidationError(
                'Debe proporcionar el motivo del rechazo.'
            )

        return cleaned_data


class BusquedaSolicitanteForm(forms.Form):
    """Formulario para buscar solicitantes."""

    busqueda = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por nombre o cédula...',
        }),
        label='Buscar'
    )


# ==================== Formularios de Administración ====================

class CrearTipoVisaForm(forms.Form):
    """Formulario para crear un nuevo tipo de visa."""

    codigo = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ej: diplomatica',
        }),
        label='Código',
        help_text='Identificador único sin espacios (se convertirá a minúsculas)'
    )

    nombre = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ej: Diplomática',
        }),
        label='Nombre'
    )

    descripcion = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Descripción opcional del tipo de visa...',
        }),
        label='Descripción'
    )

    def clean_codigo(self):
        codigo = self.cleaned_data.get('codigo')
        if codigo:
            codigo = codigo.lower().strip().replace(" ", "_")
            if TipoVisa.objects.filter(codigo=codigo).exists():
                raise forms.ValidationError(f"Ya existe un tipo de visa con el código '{codigo}'.")
        return codigo

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        if nombre:
            nombre = nombre.strip()
            if TipoVisa.objects.filter(nombre__iexact=nombre).exists():
                raise forms.ValidationError(f"Ya existe un tipo de visa con el nombre '{nombre}'.")
        return nombre


class CrearRequisitoForm(forms.Form):
    """Formulario para crear un nuevo requisito en el catálogo."""

    nombre = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ej: certificado médico',
        }),
        label='Nombre del Requisito'
    )

    descripcion = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Descripción opcional del requisito...',
        }),
        label='Descripción'
    )

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre')
        if nombre:
            nombre = nombre.strip().lower()
            if CatalogoRequisito.objects.filter(nombre__iexact=nombre).exists():
                raise forms.ValidationError(f"Ya existe un requisito con el nombre '{nombre}'.")
        return nombre


