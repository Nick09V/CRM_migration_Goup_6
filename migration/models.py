from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class Agente(models.Model):
    nombre = models.CharField("Nombre", max_length=100, unique=True)
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Agente"
        verbose_name_plural = "Agentes"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Cita(models.Model):
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_CONFIRMADA = "confirmada"
    ESTADO_CANCELADA = "cancelada"

    ESTADOS = (
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_CONFIRMADA, "Confirmada"),
        (ESTADO_CANCELADA, "Cancelada"),
    )

    cliente = models.CharField("Cliente", max_length=120)
    agente = models.ForeignKey(Agente, on_delete=models.PROTECT, related_name="citas")
    inicio = models.DateTimeField("Inicio")
    fin = models.DateTimeField("Fin")
    estado = models.CharField("Estado", max_length=20, choices=ESTADOS, default=ESTADO_PENDIENTE)
    creada_en = models.DateTimeField("Creada en", auto_now_add=True)

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas"
        # Un agente no puede tener dos citas que comiencen a la misma hora
        constraints = [
            models.UniqueConstraint(fields=["agente", "inicio"], name="uniq_agente_inicio"),
        ]
        ordering = ["inicio"]

    def __str__(self):
        return f"{self.cliente} con {self.agente} @ {self.inicio:%Y-%m-%d %H:%M}"

    def clean(self):
        # Duración de exactamente 1 hora
        if self.fin != self.inicio + timezone.timedelta(hours=1):
            raise ValidationError("La cita debe durar exactamente 1 hora.")
        # Ventana de atención 08:00-12:00 en el mismo día
        inicio_local = timezone.localtime(self.inicio)
        fin_local = timezone.localtime(self.fin)
        if inicio_local.date() != fin_local.date():
            raise ValidationError("La cita debe estar en el mismo día.")
        if not (8 <= inicio_local.hour < 12):
            raise ValidationError("La hora de inicio debe estar entre 08:00 y 12:00 (excluye 12:00).")
        if fin_local.hour != inicio_local.hour + 1:
            raise ValidationError("La cita debe terminar una hora después del inicio.")
        # Un cliente solo puede tener una cita pendiente a la vez
        existe_pendiente = Cita.objects.filter(
            cliente=self.cliente, estado=self.ESTADO_PENDIENTE
        ).exclude(pk=self.pk).exists()
        if existe_pendiente:
            raise ValidationError("El cliente ya tiene una cita pendiente.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
