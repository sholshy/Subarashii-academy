from django.db import models
from apps.catalog.models import CardPrint

class PricingRuleConfig(models.Model):
    name = models.CharField(max_length=100, default='Configuración General de Precios', verbose_name='Nombre')
    is_active = models.BooleanField(default=True, verbose_name='Activa')
    usd_to_clp_rate = models.DecimalField(max_digits=10, decimal_places=2, default=950.00, verbose_name='Tipo de Cambio USD/CLP')
    commercial_margin_percent = models.DecimalField(max_digits=5, decimal_places=2, default=25.00, verbose_name='Margen Comercial (%)')
    cash_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=5.00, verbose_name='Descuento por Efectivo (%)')
    card_processing_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=2.95, verbose_name='Costo de Procesamiento Tarjeta (%)')
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=19.00, verbose_name='IVA / Impuesto (%)')
    rounding_unit = models.PositiveIntegerField(default=100, verbose_name='Unidad de Redondeo (CLP)', help_text='Ej. 100 para redondear a centenas')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de Reglas de Precio'
        verbose_name_plural = 'Configuraciones de Reglas de Precio'

    def __str__(self) -> str:
        return f"{self.name} (USD: ${self.usd_to_clp_rate} | Margen: {self.commercial_margin_percent}%)"


class PriceQuote(models.Model):
    class Source(models.TextChoices):
        TCGPLAYER_DIRECT = 'TCGPLAYER', 'TCGplayer Oficial'
        AUTHORIZED_PROVIDER = 'PROVIDER', 'Proveedor Autorizado'
        MANUAL = 'MANUAL', 'Fijación Manual'

    card_print = models.ForeignKey(
        CardPrint,
        on_delete=models.CASCADE,
        related_name='price_quotes',
        verbose_name='Impresión'
    )
    source = models.CharField(
        max_length=30,
        choices=Source.choices,
        default=Source.MANUAL,
        verbose_name='Fuente de Cotización'
    )
    reference_price_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Precio Referencia (USD)'
    )
    usd_to_clp_rate_used = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=950.00,
        verbose_name='Tasa USD/CLP Utilizada'
    )
    calculated_cash_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Precio Final Efectivo (CLP)'
    )
    calculated_card_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Precio Final Tarjeta (CLP)'
    )
    is_current = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Cotización Vigente'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha de Cotización')

    class Meta:
        verbose_name = 'Cotización de Precio'
        verbose_name_plural = 'Historial de Cotizaciones de Precios'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"{self.card_print.print_code} - Cash: ${self.calculated_cash_price:,.0f} | Card: ${self.calculated_card_price:,.0f}"
