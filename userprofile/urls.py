from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'userprofile'
urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='userprofile/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='userprofile/logout.html'), name='logout'),
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='userprofile/password_change.html'),
         name='password_change'),
    path('password_change/done/',
         auth_views.PasswordChangeDoneView.as_view(template_name='userprofile/password_change_done.html'),
         name='password_change_done'),
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='userprofile/password_reset.html'),
         name='password_reset'),
    path('password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='userprofile/password_reset_done.html'),
         name='password_reset_done'),
    path('register/', views.register, name='register'),
    path('profile/view/', views.profile_view, name='profile_view'),
    path('profile/complete/', views.complete_profile, name='complete_profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
]
