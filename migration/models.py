from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta

# Constantes de reglas de negocio
HORA_INICIO_ATENCION = 8
HORA_FIN_ATENCION = 12
DURACION_CITA_HORAS = 1
MAXIMO_SEMANAS_ANTICIPACION = 2
DIAS_LABORALES = [0, 1, 2, 3, 4, 5]  # Lunes a Sábado

# Tipos de visa soportados
TIPO_VISA_ESTUDIANTIL = "estudiantil"
TIPO_VISA_TRABAJO = "trabajo"
TIPO_VISA_RESIDENCIAL = "residencial"
TIPO_VISA_TURISTA = "turista"

TIPOS_VISA = (
    (TIPO_VISA_ESTUDIANTIL, "Estudiantil"),
    (TIPO_VISA_TRABAJO, "Trabajo"),
    (TIPO_VISA_RESIDENCIAL, "Residencial"),
    (TIPO_VISA_TURISTA, "Turista"),
)

# Requisitos por tipo de visa
REQUISITOS_POR_VISA = {
    TIPO_VISA_ESTUDIANTIL: ["ci", "carta aceptación", "solvencia económica", "certificado idioma"],
    TIPO_VISA_TRABAJO: ["ci", "oferta laboral", "experiencia", "antecedentes", "pruebas calificación"],
    TIPO_VISA_RESIDENCIAL: ["ci", "sustento económico", "seguro médico", "acreditación arraigo"],
    TIPO_VISA_TURISTA: ["ci", "itinerario", "reserva hotel", "solvencia económica"],
}

# Estados de documentos
ESTADO_DOCUMENTO_PENDIENTE = "pendiente"
ESTADO_DOCUMENTO_REVISADO = "revisado"
ESTADO_DOCUMENTO_FALTANTE = "faltante"

ESTADOS_DOCUMENTO = (
    (ESTADO_DOCUMENTO_PENDIENTE, "Pendiente"),
    (ESTADO_DOCUMENTO_REVISADO, "Revisado"),
    (ESTADO_DOCUMENTO_FALTANTE, "Faltante"),
)

# Estados de carpeta
ESTADO_CARPETA_PENDIENTE = "pendiente"
ESTADO_CARPETA_APROBADO = "aprobado"
ESTADO_CARPETA_RECHAZADO = "rechazado"

ESTADOS_CARPETA = (
    (ESTADO_CARPETA_PENDIENTE, "Pendiente"),
    (ESTADO_CARPETA_APROBADO, "Aprobado"),
    (ESTADO_CARPETA_RECHAZADO, "Rechazado"),
)


class Solicitante(models.Model):
    """Representa a una persona que solicita citas migratorias."""
    nombre = models.CharField("Nombre", max_length=120, unique=True)
    cedula = models.CharField("Cédula", max_length=20, blank=True)
    telefono = models.CharField("Teléfono", max_length=20, blank=True)
    email = models.EmailField("Email", blank=True)
    tipo_visa = models.CharField(
        "Tipo de Visa",
        max_length=20,
        choices=TIPOS_VISA,
        blank=True,
        null=True
    )
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)

    class Meta:
        verbose_name = "Solicitante"
        verbose_name_plural = "Solicitantes"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def tiene_cita_pendiente(self):
        """Verifica si el solicitante tiene una cita pendiente activa."""
        return self.citas.filter(estado=Cita.ESTADO_PENDIENTE).exists()


class Agente(models.Model):
    """Representa a un agente que atiende citas migratorias."""
    nombre = models.CharField("Nombre", max_length=100, unique=True)
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Agente"
        verbose_name_plural = "Agentes"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Cita(models.Model):
    """Representa una cita migratoria agendada."""
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_REALIZADA = "realizada"
    ESTADO_CANCELADA = "cancelada"
    ESTADO_EXITOSA = "exitosa"

    ESTADOS = (
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_REALIZADA, "Realizada"),
        (ESTADO_CANCELADA, "Cancelada"),
        (ESTADO_EXITOSA, "Exitosa"),
    )

    solicitante = models.ForeignKey(
        Solicitante,
        on_delete=models.PROTECT,
        related_name="citas"
    )
    agente = models.ForeignKey(
        Agente,
        on_delete=models.PROTECT,
        related_name="citas"
    )
    inicio = models.DateTimeField("Inicio")
    fin = models.DateTimeField("Fin", editable=False)
    estado = models.CharField(
        "Estado",
        max_length=20,
        choices=ESTADOS,
        default=ESTADO_PENDIENTE
    )
    creada_en = models.DateTimeField("Creada en", auto_now_add=True)

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas"
        constraints = [
            models.UniqueConstraint(
                fields=["agente", "inicio"],
                name="uniq_agente_inicio"
            ),
        ]
        ordering = ["inicio"]

    def __str__(self):
        return f"{self.solicitante} con {self.agente} @ {self.inicio:%Y-%m-%d %H:%M}"

    def _calcular_fin(self):
        """Calcula automáticamente el horario de fin basado en el inicio."""
        return self.inicio + timedelta(hours=DURACION_CITA_HORAS)

    def _validar_horario_atencion(self, inicio_local):
        """Valida que la cita esté dentro del horario de atención."""
        if not (HORA_INICIO_ATENCION <= inicio_local.hour < HORA_FIN_ATENCION):
            raise ValidationError(
                f"Las citas solo pueden agendarse entre las "
                f"{HORA_INICIO_ATENCION}:00 y las {HORA_FIN_ATENCION}:00."
            )

    def _validar_dia_laboral(self, fecha):
        """Valida que la cita sea en un día laboral (lunes a sábado)."""
        if fecha.weekday() not in DIAS_LABORALES:
            raise ValidationError("No se pueden agendar citas los domingos.")

    def _validar_rango_fechas(self, fecha_cita):
        """Valida que la cita esté dentro del rango permitido (hoy hasta 2 semanas)."""
        hoy = timezone.localtime(timezone.now()).date()
        fecha_maxima = hoy + timedelta(weeks=MAXIMO_SEMANAS_ANTICIPACION)

        if fecha_cita < hoy:
            raise ValidationError("No se pueden agendar citas en fechas pasadas.")
        if fecha_cita > fecha_maxima:
            raise ValidationError(
                f"Solo se pueden agendar citas hasta {MAXIMO_SEMANAS_ANTICIPACION} "
                f"semanas a partir de hoy."
            )

    def _validar_cita_pendiente_existente(self):
        """Valida que el solicitante no tenga otra cita pendiente."""
        if self.solicitante and self.solicitante.tiene_cita_pendiente():
            # Si estamos actualizando, excluir la cita actual
            if self.pk:
                return
            raise ValidationError(
                "El solicitante ya tiene una cita pendiente. "
                "Debe cancelar la cita existente antes de agendar una nueva."
            )

    def clean(self):
        """Ejecuta todas las validaciones de la cita."""
        if not self.inicio:
            raise ValidationError("El horario de inicio es obligatorio.")

        inicio_local = timezone.localtime(self.inicio)

        self._validar_horario_atencion(inicio_local)
        self._validar_dia_laboral(inicio_local.date())
        self._validar_rango_fechas(inicio_local.date())
        self._validar_cita_pendiente_existente()

    def save(self, *args, **kwargs):
        """Guarda la cita calculando automáticamente el horario de fin."""
        self.fin = self._calcular_fin()
        self.full_clean()
        return super().save(*args, **kwargs)

    def es_fecha_cita_hoy(self) -> bool:
        """
        Verifica si la fecha de la cita coincide con la fecha actual.

        Returns:
            True si la cita es para hoy, False en caso contrario.
        """
        hoy = timezone.localtime(timezone.now()).date()
        fecha_cita = timezone.localtime(self.inicio).date()
        return fecha_cita == hoy

    def marcar_como_exitosa(self) -> None:
        """
        Marca la cita como exitosa.

        Raises:
            ValidationError: Si la cita no está en estado pendiente.
        """
        if self.estado != Cita.ESTADO_PENDIENTE:
            raise ValidationError(
                "Solo se pueden marcar como exitosas las citas pendientes."
            )
        self.estado = Cita.ESTADO_EXITOSA
        # Usar super().save() para evitar full_clean() ya que solo actualizamos el estado
        super(Cita, self).save(update_fields=["estado"])


class Requisito(models.Model):
    """Representa un requisito/documento requerido para un solicitante."""
    solicitante = models.ForeignKey(
        Solicitante,
        on_delete=models.CASCADE,
        related_name="requisitos"
    )
    nombre = models.CharField("Nombre", max_length=100)
    estado = models.CharField(
        "Estado",
        max_length=20,
        choices=ESTADOS_DOCUMENTO,
        default=ESTADO_DOCUMENTO_FALTANTE
    )
    carga_habilitada = models.BooleanField("Carga Habilitada", default=True)
    observaciones = models.TextField("Observaciones", blank=True)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)

    class Meta:
        verbose_name = "Requisito"
        verbose_name_plural = "Requisitos"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["solicitante", "nombre"],
                name="uniq_solicitante_requisito"
            ),
        ]

    def __str__(self):
        return f"{self.nombre} - {self.estado}"


class Documento(models.Model):
    """Representa un documento subido por el solicitante."""
    requisito = models.ForeignKey(
        Requisito,
        on_delete=models.CASCADE,
        related_name="documentos"
    )
    version = models.PositiveIntegerField("Versión", default=1)
    estado = models.CharField(
        "Estado",
        max_length=20,
        choices=ESTADOS_DOCUMENTO,
        default=ESTADO_DOCUMENTO_PENDIENTE
    )
    archivo = models.FileField("Archivo", upload_to="documentos/", blank=True, null=True)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ["-version"]

    def __str__(self):
        return f"{self.requisito.nombre} v{self.version} - {self.estado}"


class Carpeta(models.Model):
    """Representa una carpeta que agrupa documentos de un solicitante."""
    solicitante = models.OneToOneField(
        Solicitante,
        on_delete=models.CASCADE,
        related_name="carpeta"
    )
    estado = models.CharField(
        "Estado",
        max_length=20,
        choices=ESTADOS_CARPETA,
        default=ESTADO_CARPETA_PENDIENTE
    )
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)

    class Meta:
        verbose_name = "Carpeta"
        verbose_name_plural = "Carpetas"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Carpeta {self.solicitante.cedula} - {self.estado}"
