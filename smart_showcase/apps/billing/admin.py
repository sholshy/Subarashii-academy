from django.contrib import admin
from .models import TaxDocument

@admin.register(TaxDocument)
class TaxDocumentAdmin(admin.ModelAdmin):
    list_display = ('order', 'doc_type', 'folio', 'recipient_rut', 'total_amount', 'is_emitted', 'created_at')
    list_filter = ('doc_type', 'is_emitted')
    search_fields = ('order__order_number', 'folio', 'recipient_rut', 'recipient_name')
