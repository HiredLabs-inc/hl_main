from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "userprofile"
urlpatterns = [
    path("", views.user_home, name="user_home"),
    path("onboarding/", views.onboarding_home_view, name="onboarding_home"),
    path(
        "onboarding/profile/", views.onboarding_profile_view, name="onboarding_profile"
    ),
    path(
        "onboarding/veteran_profile/",
        views.onboarding_veteran_profile_view,
        name="onboarding_veteran_profile",
    ),
    path(
        "onboarding/service_package/",
        views.onboarding_service_package_view,
        name="onboarding_service_package",
    ),
    path(
        "onboarding/upload_resume/",
        views.onboarding_upload_resume_view,
        name="onboarding_upload_resume",
    ),
    path("profile/view/", views.profile_view, name="profile_view"),
    path("profile/update/", views.profile_update_view, name="profile_update_view"),
]
