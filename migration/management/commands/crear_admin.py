"""
Comando para crear el usuario administrador inicial.
Uso: python manage.py crear_admin
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Crea el usuario administrador inicial del sistema'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Nombre de usuario del administrador (default: admin)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='admin123',
            help='Contraseña del administrador (default: admin123)'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@crm-migracion.com',
            help='Email del administrador'
        )

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'El usuario "{username}" ya existe.')
            )
            user = User.objects.get(username=username)
            if not user.is_superuser:
                user.is_superuser = True
                user.is_staff = True
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Usuario "{username}" actualizado como superusuario.')
                )
        else:
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS(f'Usuario administrador "{username}" creado exitosamente.')
            )
            self.stdout.write(
                self.style.WARNING(f'Contraseña: {password}')
            )
            self.stdout.write(
                self.style.WARNING('¡Recuerde cambiar la contraseña en producción!')
            )
