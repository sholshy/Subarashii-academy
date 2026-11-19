from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action', 'model_name', 'object_id', 'user', 'ip_address')
    list_filter = ('action', 'model_name', 'created_at')
    search_fields = ('object_id', 'user__username', 'model_name')
    readonly_fields = [f.name for f in AuditLog._meta.fields]
