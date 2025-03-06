from django.urls import path
from . import views

app_name = 'lead_validation'

urlpatterns = [
    path('validate-lead/', views.validate_lead, name='validate_lead'),
] 