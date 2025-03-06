from django.urls import path
from . import views

app_name = 'lead_validation'

urlpatterns = [
    path('validate/<int:lead_id>/', views.validate_lead, name='validate_lead'),
] 