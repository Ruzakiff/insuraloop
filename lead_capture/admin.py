from django.contrib import admin
from .models import Lead

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'insurance_type', 'status', 'agent', 'created_at')
    list_filter = ('status', 'insurance_type', 'created_at')
    search_fields = ('name', 'email', 'phone')
    date_hierarchy = 'created_at'
