from django.contrib import admin
from .models import PaymentAttempt, WebhookLog

@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ('order', 'provider', 'amount', 'status', 'signature_verified', 'external_transaction_id', 'created_at')
    list_filter = ('provider', 'status', 'signature_verified', 'created_at')
    search_fields = ('order__order_number', 'external_transaction_id', 'idempotency_key')
    readonly_fields = ('created_at', 'updated_at', 'idempotency_key')

@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ('provider', 'event_type', 'is_valid', 'processed', 'created_at')
    list_filter = ('provider', 'is_valid', 'processed')
    readonly_fields = [f.name for f in WebhookLog._meta.fields]
