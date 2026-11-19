from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Genera un volcado JSON de las vitrinas, slots, asignaciones y reglas de precio para persistencia.'

    def handle(self, *args, **options):
        fixture_dir = settings.BASE_DIR / 'data' / 'fixtures'
        fixture_dir.mkdir(parents=True, exist_ok=True)
        fixture_file = fixture_dir / 'showcases_seed.json'

        self.stdout.write("Generando respaldo de vitrinas, slots y catálogo...")
        with open(fixture_file, 'w', encoding='utf-8') as f:
            call_command(
                'dumpdata',
                'showcases',
                'pricing',
                'catalog',
                'inventory',
                indent=2,
                stdout=f
            )

        self.stdout.write(self.style.SUCCESS(f"Respaldo generado exitosamente en {fixture_file}"))
