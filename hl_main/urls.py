"""hl_main URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from userprofile import views as userprofile_views

urlpatterns = [
    path("admin/", admin.site.urls, name="admin"),
    path("accounts/", include("allauth.urls")),
    path("accounts/sign-up/", userprofile_views.CustomSignupView.as_view(), name="custom_account_signup"),
    path(
        "accounts/verified_email_required",
        userprofile_views.verified_email_required_view,
        name="account_verified_email_required",
    ),
    path("", userprofile_views.home, name="home"),
    path("tos/", userprofile_views.terms_of_service, name="terms_of_service"),
    path("privacy/", userprofile_views.privacy_policy, name="privacy_policy"),
    path("about/", userprofile_views.about, name="about"),
    path("how_it_works/", userprofile_views.how_it_works, name="how_it_works"),
    path("contact/", userprofile_views.contact, name="contact"),
    path("donate/", userprofile_views.contact, name="donate"),
    path("impact/", userprofile_views.impact, name="impact"),
    path("volunteer/", userprofile_views.contact, name="volunteer"),
    path("thank-you/", userprofile_views.thanks, name="thanks"),
    path("welcome/", userprofile_views.welcome, name="welcome"),
    path("staff/", userprofile_views.staff, name="staff"),
    path("userprofile/", include("userprofile.urls")),
    path("cold_apply/", include("cold_apply.urls")),
    path("resume/", include("resume.urls")),
    path("releases/", include("releases.urls")),
    path("rates/", include("rates.urls")),
] + static(
    settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
)  # this only works in development

if settings.DEBUG:
    urlpatterns += [
        path("__debug__/", include("debug_toolbar.urls")),
        path("__reload__/", include("django_browser_reload.urls")),
    ]
