from django.db import models
from apps.sales.models import Order

class TaxDocument(models.Model):
    class DocType(models.TextChoices):
        BOLETA_ELECTRONICA = 'BOLETA', 'Boleta Electrónica'
        FACTURA_ELECTRONICA = 'FACTURA', 'Factura Electrónica'

    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name='tax_document', verbose_name='Orden')
    doc_type = models.CharField(max_length=20, choices=DocType.choices, default=DocType.BOLETA_ELECTRONICA)
    folio = models.CharField(max_length=50, blank=True, verbose_name='Número de Folio DTE')
    recipient_rut = models.CharField(max_length=20, blank=True, verbose_name='RUT Receptor')
    recipient_name = models.CharField(max_length=150, blank=True, verbose_name='Razón Social / Nombre')
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Monto Neto')
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='IVA')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Monto Total')
    is_emitted = models.BooleanField(default=False, verbose_name='Emitido ante SII')
    emitted_at = models.DateTimeField(null=True, blank=True)
    pdf_url = models.URLField(blank=True, verbose_name='URL Boleta/Factura PDF')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Documento Tributario'
        verbose_name_plural = 'Documentos Tributarios'

    def __str__(self) -> str:
        return f"{self.get_doc_type_display()} Folio: {self.folio or 'Pendiente'} (${self.total_amount:,.0f})"
