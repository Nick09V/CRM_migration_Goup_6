from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
import os
import unicodedata 

# Constantes de reglas de negocio
HORA_INICIO_ATENCION = 8
HORA_FIN_ATENCION = 12
DURACION_CITA_HORAS = 1
MAXIMO_SEMANAS_ANTICIPACION = 2
DIAS_LABORALES = [0, 1, 2, 3, 4, 5]  # Lunes a Sábado

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
ESTADO_CARPETA_CERRADA_ACEPTADA = "cerrada_aceptada"
ESTADO_CARPETA_CERRADA_RECHAZADA = "cerrada_rechazada"

ESTADOS_CARPETA = (
    (ESTADO_CARPETA_PENDIENTE, "Pendiente"),
    (ESTADO_CARPETA_APROBADO, "Aprobado"),
    (ESTADO_CARPETA_RECHAZADO, "Rechazado"),
    (ESTADO_CARPETA_CERRADA_ACEPTADA, "Cerrada Aceptada"),
    (ESTADO_CARPETA_CERRADA_RECHAZADA, "Cerrada Rechazada"),
)


# ============================================================================
# MODELOS DE DATOS DE REFERENCIA
# ============================================================================

class TipoVisa(models.Model):
    """
    Representa un tipo de visa disponible en el sistema.
    Los datos se crean en producción vía admin o migraciones de datos.
    En tests, se crean directamente en los steps según sea necesario.
    """
    codigo = models.CharField(
        "Código",
        max_length=30,
        unique=True,
        help_text="Identificador único del tipo de visa (ej: estudiantil)"
    )
    nombre = models.CharField(
        "Nombre",
        max_length=100,
        help_text="Nombre descriptivo del tipo de visa (ej: Estudiantil)"
    )
    activo = models.BooleanField("Activo", default=True)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)

    class Meta:
        verbose_name = "Tipo de Visa"
        verbose_name_plural = "Tipos de Visa"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @classmethod
    def obtener_tipos_activos(cls) -> list[str]:
        """Retorna una lista de códigos de tipos de visa activos."""
        return list(cls.objects.filter(activo=True).values_list('codigo', flat=True))

    @classmethod
    def obtener_por_codigo(cls, codigo: str):
        """
        Obtiene un TipoVisa por su código.

        Args:
            codigo: Código del tipo de visa.

        Returns:
            Instancia de TipoVisa o None si no existe.
        """
        return cls.objects.filter(codigo=codigo, activo=True).first()

    @classmethod
    def existe(cls, codigo: str) -> bool:
        """Verifica si existe un tipo de visa activo con el código dado."""
        return cls.objects.filter(codigo=codigo, activo=True).exists()


class TipoRequisito(models.Model):
    """
    Representa un tipo de requisito/documento disponible en el sistema.
    Define los tipos de documentos que pueden ser requeridos para visas.
    """
    codigo = models.CharField(
        "Código",
        max_length=50,
        unique=True,
        help_text="Identificador único del requisito (ej: ci)"
    )
    nombre = models.CharField(
        "Nombre",
        max_length=150,
        help_text="Nombre descriptivo del requisito (ej: Cédula de Identidad)"
    )
    descripcion = models.TextField("Descripción", blank=True)
    activo = models.BooleanField("Activo", default=True)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)

    class Meta:
        verbose_name = "Tipo de Requisito"
        verbose_name_plural = "Tipos de Requisito"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @classmethod
    def obtener_por_codigo(cls, codigo: str):
        """Obtiene un TipoRequisito por su código."""
        return cls.objects.filter(codigo=codigo, activo=True).first()


class RequisitoVisa(models.Model):
    """
    Tabla pivote que asocia requisitos con tipos de visa.
    Define qué requisitos necesita cada tipo de visa.
    """
    tipo_visa = models.ForeignKey(
        TipoVisa,
        on_delete=models.CASCADE,
        related_name="requisitos_visa"
    )
    tipo_requisito = models.ForeignKey(
        TipoRequisito,
        on_delete=models.CASCADE,
        related_name="visas_requisito"
    )
    orden = models.PositiveIntegerField(
        "Orden",
        default=0,
        help_text="Orden en que se muestra el requisito para este tipo de visa"
    )
    obligatorio = models.BooleanField("Obligatorio", default=True)

    class Meta:
        verbose_name = "Requisito por Visa"
        verbose_name_plural = "Requisitos por Visa"
        ordering = ["tipo_visa", "orden"]
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_visa", "tipo_requisito"],
                name="uniq_tipovisa_tiporequisito"
            ),
        ]

    def __str__(self):
        return f"{self.tipo_visa.codigo} - {self.tipo_requisito.codigo}"

    @classmethod
    def obtener_requisitos_por_visa(cls, tipo_visa_codigo: str) -> list[str]:
        """
        Obtiene los códigos de requisitos para un tipo de visa.

        Args:
            tipo_visa_codigo: Código del tipo de visa.

        Returns:
            Lista de códigos de requisitos ordenados.
        """
        return list(
            cls.objects.filter(
                tipo_visa__codigo=tipo_visa_codigo,
                tipo_visa__activo=True,
                tipo_requisito__activo=True
            ).order_by('orden').values_list('tipo_requisito__codigo', flat=True)
        )


# ============================================================================
# MODELOS PRINCIPALES DEL SISTEMA
# ============================================================================

class Solicitante(models.Model):
    """Representa a una persona que solicita citas migratorias."""
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='solicitante',
        null=True,
        blank=True
    )
    nombre = models.CharField("Nombre", max_length=120, unique=True)
    cedula = models.CharField("Cédula", max_length=20, unique=True, null=True, blank=True)
    telefono = models.CharField("Teléfono", max_length=20, blank=True)
    email = models.EmailField("Email", blank=True)
    tipo_visa = models.CharField("Tipo de Visa", max_length=30, blank=True)
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)

    class Meta:
        verbose_name = "Solicitante"
        verbose_name_plural = "Solicitantes"
        ordering = ["-creado_en"]

    def __str__(self):
        return self.nombre

    def tiene_cita_pendiente(self) -> bool:
        """Verifica si el solicitante tiene una cita pendiente."""
        return self.citas.filter(estado='pendiente').exists()

    def obtener_progreso(self):
        """Calcula el porcentaje de documentos revisados."""
        total = self.requisitos.count()
        if total == 0:
            return 0
        
        # OJO: Asegúrate que 'revisado' es exactamente como lo guardas en BD (minúsculas)
        aprobados = self.requisitos.filter(estado='revisado').count()
        
        return int((aprobados / total) * 100)


class Agente(models.Model):
    """Representa a un agente que atiende citas."""
    usuario = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        related_name='agente', 
        null=True,
        blank=True
    )
    nombre = models.CharField("Nombre", max_length=120)
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Agente"
        verbose_name_plural = "Agentes"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def clean(self):
        """Validación personalizada."""
        if self.activo is None:
            raise ValidationError("El campo 'activo' no puede estar vacío.")

    @classmethod
    def activos_disponibles(cls):
        """Retorna un queryset de agentes activos."""
        return cls.objects.filter(activo=True)


class Cita(models.Model):
    """Representa una cita agendada entre un solicitante y un agente."""

    # Estados posibles de una cita
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_EXITOSA = "exitosa"
    ESTADO_CANCELADA = "cancelada"
    ESTADO_FALLIDA = "fallida"

    ESTADOS_CITA = (
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_EXITOSA, "Exitosa"),
        (ESTADO_CANCELADA, "Cancelada"),
        (ESTADO_FALLIDA, "Fallida"),
    )

    solicitante = models.ForeignKey(
        Solicitante,
        on_delete=models.CASCADE,
        related_name="citas"
    )
    agente = models.ForeignKey(
        Agente,
        on_delete=models.CASCADE,
        related_name="citas"
    )
    inicio = models.DateTimeField("Inicio")
    fin = models.DateTimeField("Fin", null=True, blank=True)
    estado = models.CharField(
        "Estado",
        max_length=20,
        choices=ESTADOS_CITA,
        default=ESTADO_PENDIENTE
    )
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)

    class Meta:
        verbose_name = "Cita"
        verbose_name_plural = "Citas"
        ordering = ["-inicio"]

    def __str__(self):
        return f"Cita {self.solicitante.nombre} - {self.inicio.strftime('%Y-%m-%d %H:%M')}"

    def _calcular_fin(self):
        """Calcula la hora de fin basándose en la hora de inicio."""
        return self.inicio + timedelta(hours=DURACION_CITA_HORAS)

    def save(self, *args, **kwargs):
        """Sobrescribe save para calcular automáticamente el fin."""
        if not self.fin:
            self.fin = self._calcular_fin()
        super().save(*args, **kwargs)

    def es_fecha_cita_hoy(self) -> bool:
        """Verifica si la cita es para el día de hoy."""
        hoy = timezone.localtime(timezone.now()).date()
        fecha_cita = timezone.localtime(self.inicio).date()
        return fecha_cita == hoy

    def marcar_como_exitosa(self):
        """Marca la cita como exitosa."""
        self.estado = self.ESTADO_EXITOSA
        self.save(update_fields=["estado"])

    def clean(self):
        """Validaciones personalizadas de la cita."""
        if not self.inicio:
            return

        inicio_local = timezone.localtime(self.inicio)
        ahora = timezone.localtime(timezone.now())

        # Validar que la cita sea en día laboral
        if inicio_local.weekday() not in DIAS_LABORALES:
            raise ValidationError("Las citas solo pueden agendarse en días laborales (lunes a sábado).")

        # Validar que la cita esté dentro del horario de atención
        if inicio_local.hour < HORA_INICIO_ATENCION or inicio_local.hour >= HORA_FIN_ATENCION:
            raise ValidationError(
                f"Las citas solo pueden agendarse entre las {HORA_INICIO_ATENCION}:00 "
                f"y las {HORA_FIN_ATENCION}:00."
            )

        # Validar que la cita sea dentro de las próximas semanas permitidas
        diferencia = (inicio_local.date() - ahora.date()).days
        if diferencia > (MAXIMO_SEMANAS_ANTICIPACION * 7):
            raise ValidationError(
                f"Las citas solo pueden agendarse con máximo "
                f"{MAXIMO_SEMANAS_ANTICIPACION} semanas de anticipación."
            )

        # Validar que la cita no sea en el pasado
        if inicio_local < ahora:
            raise ValidationError("No se pueden agendar citas en el pasado.")


class Requisito(models.Model):
    """Representa un requisito asignado a un solicitante."""
    solicitante = models.ForeignKey(
        Solicitante,
        on_delete=models.CASCADE,
        related_name="requisitos"
    )
    nombre = models.CharField("Nombre", max_length=200)
    estado = models.CharField(
        "Estado",
        max_length=20,
        choices=ESTADOS_DOCUMENTO,
        default=ESTADO_DOCUMENTO_FALTANTE
    )
    carga_habilitada = models.BooleanField("Carga Habilitada", default=True)
    observaciones = models.TextField("Observaciones", blank=True, default="")
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)

    class Meta:
        verbose_name = "Requisito"
        verbose_name_plural = "Requisitos"
        ordering = ["solicitante", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["solicitante", "nombre"],
                name="uniq_solicitante_requisito"
            ),
        ]

    def __str__(self):
        return f"{self.solicitante.nombre} - {self.nombre}"

    def obtener_ultima_version(self) -> int:
        """
        Obtiene el número de la última versión del documento.

        Returns:
            Número de la última versión, o 0 si no hay documentos.
        """
        ultimo = self.documentos.order_by("-version").first()
        return ultimo.version if ultimo else 0

    def obtener_documento_actual(self):
        """
        Obtiene el documento con la versión más alta.

        Returns:
            Documento con la versión más alta, o None si no hay documentos.
        """
        return self.documentos.order_by("-version").first()

    def puede_subir_nuevo_documento(self) -> bool:
        """
        Verifica si se puede subir un nuevo documento.

        Returns:
            True si se puede subir un nuevo documento.
        """
        if not self.carga_habilitada:
            return False

        documento_actual = self.obtener_documento_actual()
        if documento_actual is None:
            return True

        # Solo puede subir si el último fue rechazado
        return documento_actual.estado == ESTADO_DOCUMENTO_FALTANTE

    def habilitar_carga(self) -> None:
        """Habilita la carga de documentos para este requisito."""
        self.carga_habilitada = True
        self.save(update_fields=["carga_habilitada"])

    def deshabilitar_carga(self) -> None:
        """Deshabilita la carga de documentos para este requisito."""
        self.carga_habilitada = False
        self.save(update_fields=["carga_habilitada"])

    def actualizar_estado_segun_documento(self) -> None:
        """Actualiza el estado del requisito según el estado del último documento."""
        documento_actual = self.obtener_documento_actual()
        if documento_actual:
            self.estado = documento_actual.estado
            self.save(update_fields=["estado"])

def generar_ruta_documento(instance, filename):
    """
    Calcula la ruta física donde se guardará el archivo.
    Estructura: Documentos/Cedula/TipoVisa/Requisito/vN_nombre.pdf
    """
    solicitante = instance.requisito.solicitante
    cedula = solicitante.cedula or "SIN_CEDULA"
    
    # Limpiamos espacios para evitar errores en URLs
    tramite = (solicitante.tipo_visa or "GENERAL").replace(" ", "_")
    nombre_req = instance.requisito.nombre.replace(" ", "_")
    
    # Obtenemos la extensión original (.pdf, .jpg)
    extension = filename.split('.')[-1]
    
    # Construimos el nombre final: v1_Pasaporte.pdf
    nuevo_nombre = f"v{instance.version}_{nombre_req}.{extension}"
    
    return f"Documentos/{cedula}/{tramite}/{nombre_req}/{nuevo_nombre}"


# ============================================================================
# FUNCIÓN AUXILIAR (Debe ir ANTES de la clase Documento)
# ============================================================================


# ...

def generar_ruta_documento(instance, filename):
    solicitante = instance.requisito.solicitante
    cedula = solicitante.cedula or "SIN_CEDULA"
    
    # Función auxiliar para limpiar acentos (tíldes)
    def limpiar(texto):
        texto = texto.replace(" ", "_")
        return ''.join((c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn'))

    tramite = limpiar(solicitante.tipo_visa or "GENERAL")
    nombre_req = limpiar(instance.requisito.nombre)
    
    extension = filename.split('.')[-1]
    nuevo_nombre = f"v{instance.version}_{nombre_req}.{extension}"
    
    return f"Documentos/{cedula}/{tramite}/{nombre_req}/{nuevo_nombre}"


class Documento(models.Model):
    """Representa un documento subido por el solicitante."""
    requisito = models.ForeignKey(
        Requisito,
        on_delete=models.CASCADE,
        related_name="documentos"
    )
    version = models.PositiveIntegerField("Versión", default=1)
    

    archivo = models.FileField(
        upload_to=generar_ruta_documento, 
        blank=True, 
        null=True,
        verbose_name="Archivo subido"
    )
    
    estado = models.CharField(
        "Estado",
        max_length=20,
        choices=ESTADOS_DOCUMENTO,
        default=ESTADO_DOCUMENTO_PENDIENTE
    )
    
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)

    class Meta:
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["requisito", "version"],
                name="uniq_requisito_version"
            ),
        ]

    def __str__(self):
        return f"{self.requisito.nombre} v{self.version} - {self.estado}"

    # --- MÉTODOS ÚTILES ---

    def obtener_url(self):
        """Retorna la URL pública para ver el archivo en el navegador."""
        if self.archivo:
            return self.archivo.url
        return "#"

    def es_version_pendiente(self) -> bool:
        """Verifica si el documento está en estado pendiente."""
        return self.estado == ESTADO_DOCUMENTO_PENDIENTE

    def es_version_rechazada(self) -> bool:
        """Verifica si el documento ha sido rechazado (faltante)."""
        return self.estado == ESTADO_DOCUMENTO_FALTANTE

    def marcar_como_pendiente(self) -> None:
        """Marca el documento como pendiente de revisión."""
        self.estado = ESTADO_DOCUMENTO_PENDIENTE
        self.save(update_fields=["estado"])

    def marcar_como_revisado(self) -> None:
        """Marca el documento como revisado/aprobado."""
        self.estado = ESTADO_DOCUMENTO_REVISADO
        self.save(update_fields=["estado"])

    def marcar_como_faltante(self) -> None:
        """Marca el documento como faltante/rechazado."""
        self.estado = ESTADO_DOCUMENTO_FALTANTE
        self.save(update_fields=["estado"])



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
    observaciones = models.TextField(
        "Observaciones",
        blank=True,
        default=""
    )
    creado_en = models.DateTimeField("Creado en", auto_now_add=True)

    class Meta:
        verbose_name = "Carpeta"
        verbose_name_plural = "Carpetas"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Carpeta {self.solicitante.cedula} - {self.estado}"

    def obtener_ruta_base(self) -> str:
        """
        Obtiene la ruta base de la carpeta del solicitante.
        Estructura: Documentos/CI_solicitante/tipoVisa/

        Returns:
            Ruta base de la carpeta.
        """
        cedula = self.solicitante.cedula or "SIN_CEDULA"
        tipo_visa = self.solicitante.tipo_visa or "SIN_VISA"
        return f"Documentos/{cedula}/{tipo_visa}"

    def obtener_documentos_pendientes(self):
        """
        Obtiene todos los documentos pendientes de revisión del solicitante.

        Returns:
            QuerySet de documentos pendientes.
        """
        return Documento.objects.filter(
            requisito__solicitante=self.solicitante,
            estado=ESTADO_DOCUMENTO_PENDIENTE
        )

    def tiene_documentos_pendientes(self) -> bool:
        """Verifica si hay documentos pendientes de revisión."""
        return self.obtener_documentos_pendientes().exists()

    def todos_documentos_revisados(self) -> bool:
        """
        Verifica si todos los documentos han sido revisados.

        Returns:
            True si todos los documentos están revisados.
        """
        documentos = Documento.objects.filter(
            requisito__solicitante=self.solicitante
        )
        if not documentos.exists():
            return False
        return all(doc.estado == ESTADO_DOCUMENTO_REVISADO for doc in documentos)
