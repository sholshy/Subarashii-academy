from django.core.management.base import BaseCommand
from apps.pricing.exchange_service import ExchangeRateService

class Command(BaseCommand):
    help = 'Actualiza el valor del dólar USD/CLP desde APIs financieras en tiempo real y opcionalmente recalcula cotizaciones.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--recalculate',
            action='store_true',
            help='Recalcula todas las cotizaciones vigentes con la nueva tasa'
        )

    def handle(self, *args, **options):
        recalculate = options.get('recalculate', False)
        self.stdout.write("Consultando tipo de cambio USD/CLP desde API pública...")
        
        rate, count = ExchangeRateService.update_config_rate(auto_recalculate=recalculate)
        if rate:
            self.stdout.write(self.style.SUCCESS(f"Dólar actualizado con éxito: $1 USD = ${rate} CLP"))
            if recalculate:
                self.stdout.write(self.style.SUCCESS(f"Se recalcularon {count} cotizaciones vigentes."))
        else:
            self.stdout.write(self.style.ERROR("No fue posible obtener el tipo de cambio desde las APIs disponibles."))
