from django.urls import path

from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='auth-register'),
    path('verify-email/', views.VerifyEmailView.as_view(), name='auth-verify-email'),
    path('token/', views.LoginView.as_view(), name='auth-login'),
    path('token/refresh/', views.TokenRefreshView.as_view(), name='auth-token-refresh'),
    path('logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('password-reset/', views.PasswordResetRequestView.as_view(), name='auth-password-reset'),
    path('password-reset/confirm/', views.PasswordResetConfirmView.as_view(), name='auth-password-reset-confirm'),
]

