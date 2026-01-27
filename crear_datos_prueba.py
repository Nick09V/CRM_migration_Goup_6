"""Script para crear datos de prueba del dashboard de cliente."""

import os
import django
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mi_proyecto.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from migration.models import Solicitante, Agente, Cita, Carpeta, Requisito

print('=== CREANDO DATOS DE PRUEBA ===\n')

# 1. Usuario cliente
user_cliente = User.objects.filter(username='usuario').first()
if not user_cliente:
    print('❌ Usuario "usuario" no encontrado. Créalo primero.')
    exit(1)

print(f'✓ Usuario encontrado: {user_cliente.username}')

# 2. Solicitante
solicitante, created = Solicitante.objects.get_or_create(
    usuario=user_cliente,
    defaults={
        'nombre': 'Usuario Cliente',
        'email': 'usuario@example.com'
    }
)
print(f'✓ Solicitante: {solicitante.nombre} {"(creado)" if created else "(existente)"}')

# 3. Carpeta
carpeta, created = Carpeta.objects.get_or_create(
    solicitante=solicitante,
    defaults={'tipo_visa': 'Turista'}
)
print(f'✓ Carpeta: Visa {carpeta.tipo_visa} {"(creada)" if created else "(existente)"}')

# 4. Requisitos
requisitos_data = [
    ('Pasaporte vigente', 'faltante'),
    ('Fotografía reciente', 'faltante'),
    ('Comprobante de domicilio', 'pendiente'),
    ('Estados de cuenta bancarios', 'faltante'),
    ('Carta de invitación', 'revisado'),
]

for nombre, estado in requisitos_data:
    req, created = Requisito.objects.get_or_create(
        carpeta=carpeta,
        nombre=nombre,
        defaults={'estado': estado}
    )
    print(f'  - {nombre}: {estado}')

print(f'✓ {len(requisitos_data)} requisitos creados/actualizados')

# 5. Agente (necesario para la cita)
agente = Agente.objects.first()
if not agente:
    print('⚠ No hay agentes. Creando agente de prueba...')
    user_agente, _ = User.objects.get_or_create(
        username='agente1',
        defaults={'email': 'agente@example.com'}
    )
    user_agente.set_password('password123')
    user_agente.save()
    
    agente, _ = Agente.objects.get_or_create(
        usuario=user_agente,
        defaults={'nombre': 'Agente Prueba', 'activo': True}
    )

print(f'✓ Agente: {agente.nombre}')

# 6. Cita pendiente (en 5 días, a las 10:00 AM - dentro del horario de atención 8-12)
# Usar timezone aware datetime
ahora = timezone.now()
fecha_cita = ahora + timedelta(days=5)
# Asegurar que sea un día laboral (lunes a sábado, no domingo)
while fecha_cita.weekday() == 6:  # 6 = Domingo
    fecha_cita += timedelta(days=1)

# Convertir a hora local y establecer hora de cita
fecha_cita_local = timezone.localtime(fecha_cita)
fecha_cita = fecha_cita_local.replace(hour=10, minute=0, second=0, microsecond=0)

# Eliminar citas pendientes previas para evitar duplicados
Cita.objects.filter(solicitante=solicitante, estado='pendiente').delete()

try:
    cita = Cita.objects.create(
        solicitante=solicitante,
        agente=agente,
        inicio=fecha_cita,
        estado='pendiente'
    )
    print(f'✓ Cita creada: {cita.inicio.strftime("%d/%m/%Y a las %H:%M")}')
    print(f'  ¿Puede cancelar? {cita.puede_cancelar()} (más de 3 días)')
except Exception as e:
    print(f'❌ Error al crear cita: {e}')
    print(f'   Fecha intentada: {fecha_cita}')

print('\n=== DATOS CREADOS EXITOSAMENTE ===')
print(f'\nPrueba iniciando sesión con:')
print(f'  Usuario: usuario')
print(f'  Contraseña: (la que configuraste)')
