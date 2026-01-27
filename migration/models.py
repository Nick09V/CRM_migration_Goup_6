from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta

# Constantes de reglas de negocio
HORA_INICIO_ATENCION = 8
HORA_FIN_ATENCION = 12
DURACION_CITA_HORAS = 1
MAXIMO_SEMANAS_ANTICIPACION = 2
DIAS_LABORALES = [0, 1, 2, 3, 4, 5]  # Lunes a Sábado


class Solicitante(models.Model):
    """Representa a una persona que solicita citas migratorias."""
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='solicitante', null=True, blank=True)
    nombre = models.CharField("Nombre", max_length=120, unique=True)
    telefono = models.CharField("Teléfono", max_length=20, blank=True)
    email = models.EmailField("Email", blank=True)
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
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='agente', null=True, blank=True)
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

    ESTADOS = (
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_REALIZADA, "Realizada"),
        (ESTADO_CANCELADA, "Cancelada"),
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

    def puede_cancelar(self):
        """Verifica si la cita puede ser cancelada (más de 3 días de anticipación)."""
        if self.estado != self.ESTADO_PENDIENTE:
            return False
        
        ahora = timezone.now()
        dias_restantes = (self.inicio - ahora).days
        return dias_restantes >= 3


class Carpeta(models.Model):
    """Representa el expediente completo de un solicitante."""
    ESTADO_ABIERTO = "abierto"
    ESTADO_APROBADO = "aprobado"
    ESTADO_CERRADO = "cerrado"

    ESTADOS = (
        (ESTADO_ABIERTO, "Abierto"),
        (ESTADO_APROBADO, "Aprobado"),
        (ESTADO_CERRADO, "Cerrado"),
    )

    solicitante = models.OneToOneField(
        Solicitante,
        on_delete=models.CASCADE,
        related_name="carpeta"
    )
    tipo_visa = models.CharField("Tipo de Visa", max_length=50)
    estado = models.CharField(
        "Estado",
        max_length=20,
        choices=ESTADOS,
        default=ESTADO_ABIERTO
    )
    creada_en = models.DateTimeField("Creada en", auto_now_add=True)
    actualizada_en = models.DateTimeField("Actualizada en", auto_now=True)

    class Meta:
        verbose_name = "Carpeta"
        verbose_name_plural = "Carpetas"
        ordering = ["-creada_en"]

    def __str__(self):
        return f"Carpeta de {self.solicitante.nombre} - {self.tipo_visa}"

    def calcular_progreso(self):
        """Calcula el porcentaje de requisitos completados."""
        total_requisitos = self.requisitos.count()
        if total_requisitos == 0:
            return 0
        
        requisitos_revisados = self.requisitos.filter(estado=Requisito.ESTADO_REVISADO).count()
        return int((requisitos_revisados / total_requisitos) * 100)


class Requisito(models.Model):
    """Representa un requisito documental necesario para una visa."""
    ESTADO_FALTANTE = "faltante"
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_REVISADO = "revisado"

    ESTADOS = (
        (ESTADO_FALTANTE, "Faltante"),
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_REVISADO, "Revisado"),
    )

    carpeta = models.ForeignKey(
        Carpeta,
        on_delete=models.CASCADE,
        related_name="requisitos"
    )
    nombre = models.CharField("Nombre del Requisito", max_length=150)
    estado = models.CharField(
        "Estado",
        max_length=20,
        choices=ESTADOS,
        default=ESTADO_FALTANTE
    )
    habilitado_para_subir = models.BooleanField("Habilitado para Subir", default=True)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)

    class Meta:
        verbose_name = "Requisito"
        verbose_name_plural = "Requisitos"
        ordering = ["nombre"]
        unique_together = [["carpeta", "nombre"]]

    def __str__(self):
        return f"{self.nombre} - {self.get_estado_display()}"


class Documento(models.Model):
    """Representa un documento subido para cumplir un requisito."""
    requisito = models.ForeignKey(
        Requisito,
        on_delete=models.CASCADE,
        related_name="documentos"
    )
    archivo = models.FileField("Archivo", upload_to="documentos/%Y/%m/", blank=True, null=True)
    version = models.PositiveIntegerField("Versión", default=1)
    observaciones = models.TextField("Observaciones del Agente", blank=True)
    aprobado = models.BooleanField("Aprobado", default=False)
    subido_en = models.DateTimeField("Subido en", auto_now_add=True)

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ["-version", "-subido_en"]

    def __str__(self):
        return f"{self.requisito.nombre} v{self.version}"

    def save(self, *args, **kwargs):
        """Al guardar un documento, actualiza el estado del requisito."""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Actualizar estado del requisito a pendiente cuando se sube documento
            if self.requisito.estado == Requisito.ESTADO_FALTANTE:
                self.requisito.estado = Requisito.ESTADO_PENDIENTE
                self.requisito.save()
