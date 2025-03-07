from django.urls import path
from . import views

app_name = 'lead_validation'

urlpatterns = [
    # API endpoint for validating leads
    path('api/validate-lead/', views.validate_lead_api, name='validate_lead_api'),
    
    # View for validating an existing lead (using validate_lead as the name to match template)
    path('validate-lead/<int:lead_id>/', views.validate_existing_lead, name='validate_lead'),
] 