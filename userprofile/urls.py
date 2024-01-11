from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "userprofile"
urlpatterns = [
    path("", views.user_home, name="user_home"),
    path("onboarding/signup/", views.onboarding_view, name="onboarding_view"),
    path("profile/view/", views.profile_view, name="profile_view"),
    path("profile/update/", views.profile_update_view, name="profile_update_view"),
    path("profile/update/veteran_status/<int:participant_id>/", views.update_veteran_status_view, name="veteran_status_update_view"),
]
