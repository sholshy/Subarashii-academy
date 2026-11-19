import os
from django.core.management.base import BaseCommand
from apps.accounts.models import CustomUser

class Command(BaseCommand):
    help = 'Inicializa automáticamente el superusuario administrador para Render y producción.'

    def handle(self, *args, **options):
        username = os.environ.get('ADMIN_USERNAME', 'admin').strip()
        email = os.environ.get('ADMIN_EMAIL', 'admin@subarashii.cl').strip()
        password = os.environ.get('ADMIN_PASSWORD', 'subarashii2026').strip()

        user, created = CustomUser.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'role': CustomUser.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            }
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Superusuario '{username}' creado exitosamente."))
        else:
            # Asegurar permisos y actualizar contraseña para garantizar acceso
            user.is_staff = True
            user.is_superuser = True
            user.role = CustomUser.Role.ADMIN
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Superusuario '{username}' ya existía. Permisos y credenciales actualizados."))
