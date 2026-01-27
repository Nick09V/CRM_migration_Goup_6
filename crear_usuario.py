"""Script para crear un nuevo usuario cliente."""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mi_proyecto.settings')
django.setup()

from django.contrib.auth.models import User
from migration.models import Solicitante

print('=== CREANDO NUEVO USUARIO CLIENTE ===\n')

# Crear usuario
username = 'cliente1'
password = 'cliente123'
email = 'cliente1@example.com'

# Verificar si ya existe
if User.objects.filter(username=username).exists():
    print(f'⚠️  El usuario "{username}" ya existe.')
    user = User.objects.get(username=username)
else:
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password
    )
    print(f'✓ Usuario creado: {user.username}')

# Crear solicitante
if hasattr(user, 'solicitante'):
    print(f'✓ Solicitante ya existe: {user.solicitante.nombre}')
else:
    solicitante = Solicitante.objects.create(
        usuario=user,
        nombre='Cliente Demo',
        email=email,
        telefono='+1234567890'
    )
    print(f'✓ Solicitante creado: {solicitante.nombre}')

print('\n=== CREDENCIALES PARA LOGIN ===')
print(f'Usuario: {username}')
print(f'Contraseña: {password}')
print(f'\nAccede en: http://127.0.0.1:8000/login/')
