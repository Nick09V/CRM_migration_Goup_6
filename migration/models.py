from django.db import models
from django.utils import timezone

# Create your models here.

class Solicitante(models.Model):
    cedula = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=120)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return f"{self.cedula} - {self.nombre}"


class Agente(models.Model):
    nombre = models.CharField(max_length=120)
    carga_pendiente = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.nombre


class Cita(models.Model):
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_COMPLETADA = 'completada'
    ESTADO_CANCELADA = 'cancelada'
    ESTADOS = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_COMPLETADA, 'Completada'),
        (ESTADO_CANCELADA, 'Cancelada'),
    ]

    solicitante = models.ForeignKey(Solicitante, on_delete=models.CASCADE, related_name='citas')
    agente = models.ForeignKey(Agente, on_delete=models.SET_NULL, null=True, blank=True, related_name='citas')
    fecha_hora = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_PENDIENTE)

    def __str__(self):
        return f"Cita {self.id} - {self.solicitante.cedula} - {self.estado}"


class SolicitudVisa(models.Model):
    TIPO_ESTUDIANTIL = 'estudiantil'
    TIPO_TRABAJO = 'trabajo'
    TIPO_RESIDENCIAL = 'residencial'
    TIPOS_VISA = [
        (TIPO_ESTUDIANTIL, 'Estudiantil'),
        (TIPO_TRABAJO, 'Trabajo'),
        (TIPO_RESIDENCIAL, 'Residencial'),
    ]

    ESTADO_ABIERTO = 'abierto'
    ESTADO_NO_COMPLETADO = 'no_completado'
    ESTADO_CERRADO = 'cerrado'
    ESTADOS_EXPEDIENTE = [
        (ESTADO_ABIERTO, 'Abierto'),
        (ESTADO_NO_COMPLETADO, 'No Completado'),
        (ESTADO_CERRADO, 'Cerrado'),
    ]

    solicitante = models.ForeignKey(Solicitante, on_delete=models.CASCADE, related_name='solicitudes')
    tipo_visa = models.CharField(max_length=20, choices=TIPOS_VISA)
    estado_expediente = models.CharField(max_length=20, choices=ESTADOS_EXPEDIENTE, default=ESTADO_ABIERTO)
    carpeta_ruta = models.CharField(max_length=255, blank=True, default='')

    def __str__(self):
        return f"Solicitud {self.id} - {self.tipo_visa} - {self.solicitante.cedula}"


class Documento(models.Model):
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_REVISADO = 'revisado'
    ESTADO_FALTANTE = 'faltante'
    ESTADOS_REVISION = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_REVISADO, 'Revisado'),
        (ESTADO_FALTANTE, 'Faltante'),
    ]

    solicitud_visa = models.ForeignKey(SolicitudVisa, on_delete=models.CASCADE, related_name='documentos')
    nombre = models.CharField(max_length=120)
    estado_revision = models.CharField(max_length=20, choices=ESTADOS_REVISION, default=ESTADO_PENDIENTE)
    ruta_archivo = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        unique_together = ('solicitud_visa', 'nombre')

    def __str__(self):
        return f"{self.nombre} - {self.estado_revision}"
