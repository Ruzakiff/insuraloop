from django.urls import path
from . import views

app_name = 'lead_capture'

urlpatterns = [
    path('submit/<str:code>/', views.lead_capture, name='lead_form'),
    path('thank-you/<int:lead_id>/', views.thank_you, name='thank_you'),
    path('test-email/<int:lead_id>/', views.test_email, name='test_email'),
] 