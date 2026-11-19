import os
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management import call_command
from apps.showcases.models import Showcase
from apps.showcases.services import ShowcaseService
from apps.pricing.models import PricingRuleConfig

class Command(BaseCommand):
    help = 'Garantiza la existencia de al menos una vitrina activa con slots y QRs permanentes tras reinicios o despliegues.'

    def handle(self, *args, **options):
        fixture_path = settings.BASE_DIR / 'data' / 'fixtures' / 'showcases_seed.json'

        # Si ya existen vitrinas, no sobreescribir
        if Showcase.objects.filter(is_active=True).exists():
            self.stdout.write(self.style.SUCCESS(f"Ya existen {Showcase.objects.count()} vitrinas registradas."))
            return

        # Intentar cargar desde respaldo si existe
        if fixture_path.exists():
            try:
                self.stdout.write(f"Cargando respaldo desde {fixture_path}...")
                call_command('loaddata', str(fixture_path), verbosity=0)
                self.stdout.write(self.style.SUCCESS("Respaldo de vitrinas restaurado exitosamente."))
                return
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"No se pudo cargar fixture ({e}), generando vitrina base..."))

        # Crear Vitrina Principal inicial para evitar pantallas vacías
        showcase, slots_count = ShowcaseService.create_showcase(
            name="Vitrina Principal Yu-Gi-Oh!",
            code="VIT-01",
            total_rows=4,
            total_columns=8,
            description="Vitrina principal de exhibición en tienda física con 32 espacios y códigos QR permanentes.",
            contact_whatsapp="+56912345678"
        )

        # Garantizar reglas de precio base
        if not PricingRuleConfig.objects.exists():
            PricingRuleConfig.objects.create(
                name="Configuración General Subarashii",
                usd_to_clp_rate=1016.40,
                commercial_margin_percent=25.00,
                cash_discount_percent=5.00,
                card_processing_fee_percent=2.95,
                store_whatsapp_number="+56912345678"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Vitrina base '{showcase.name}' creada exitosamente con {slots_count} slots y códigos QR permanentes."
            )
        )
