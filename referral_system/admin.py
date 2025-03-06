from django.contrib import admin
from .models import ReferralLink, PaymentRate

@admin.register(ReferralLink)
class ReferralLinkAdmin(admin.ModelAdmin):
    list_display = ('code', 'user', 'insurance_type', 'target_state', 'created_at', 'clicks', 'conversions', 'paid_conversions')
    list_filter = ('insurance_type', 'target_state', 'is_active')
    search_fields = ('code', 'user__username', 'partner_name')
    readonly_fields = ('id', 'code', 'created_at', 'clicks', 'conversions')

@admin.register(PaymentRate)
class PaymentRateAdmin(admin.ModelAdmin):
    list_display = ('get_state_display', 'insurance_type', 'rate_amount', 'is_active', 'effective_from', 'effective_to')
    list_filter = ('insurance_type', 'is_active', 'state')
    list_editable = ('rate_amount', 'is_active')
    
    def get_state_display(self, obj):
        if obj.state == '':
            return 'Nationwide (Default)'
        return dict(PaymentRate.STATE_CHOICES).get(obj.state)
    get_state_display.short_description = 'State'
