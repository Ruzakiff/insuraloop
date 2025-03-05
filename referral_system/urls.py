from django.urls import path
from . import views

app_name = 'referral_system'

urlpatterns = [
    path('ref/<str:code>/', views.referral_landing, name='referral_landing'),
    path('generate-link/', views.generate_referral_link, name='generate_referral_link'),
    path('my-links/', views.my_referral_links, name='my_referral_links'),
]
