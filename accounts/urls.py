from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('debug-csrf/', views.debug_csrf, name='debug_csrf'),  # For debugging
    path('test-form/', views.test_form, name='test_form'),
    # We'll add registration later
]
