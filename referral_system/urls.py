from django.urls import path, register_converter
from . import views

app_name = 'referral_system'

# Add UUID converter for URL patterns
class UUIDConverter:
    regex = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    
    def to_python(self, value):
        from uuid import UUID
        return UUID(value)
    
    def to_url(self, value):
        return str(value)

# Register the UUID converter
register_converter(UUIDConverter, 'uuid')

urlpatterns = [
    path('ref/<str:code>/', views.referral_landing, name='referral_landing'),
    path('generate-link/', views.generate_referral_link, name='generate_referral_link'),
    path('my-links/', views.my_links, name='my_links'),
    path('disclaimer/', views.disclaimer, name='disclaimer'),
    path('links/<uuid:link_id>/qr/download/', views.download_qr_code, name='download_qr_code'),
    path('qr-code/<uuid:link_id>/', views.view_qr_code, name='view_qr_code'),
    path('leads/<uuid:link_id>/', views.view_leads, name='view_leads'),
    path('lead-details/<int:lead_id>/', views.view_lead_details, name='view_lead_details'),
    path('download-qr-code/<uuid:link_id>/', views.download_qr_code, name='download_qr_code'),
]
