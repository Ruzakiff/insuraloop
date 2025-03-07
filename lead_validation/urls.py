from django.urls import path
from . import views

app_name = 'lead_validation'

urlpatterns = [
    # API endpoint for validating leads via AJAX
    path('api/validate-lead/', views.validate_lead_api, name='validate_lead_api'),
    
    # View for validating an existing lead (this is what the template is looking for)
    path('validate-lead/<int:lead_id>/', views.validate_existing_lead, name='validate_lead'),
] 