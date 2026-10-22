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
from django.views.generic import RedirectView

from pipeline import views as pipeline_views
from userprofile import people, signup, stuck_signups, views as userprofile_views

urlpatterns = [
    path("admin/", admin.site.urls, name="admin"),
    # Signup lives in userprofile.signup; allauth's own signup URL redirects there.
    path("accounts/signup/", RedirectView.as_view(pattern_name="custom_account_signup")),
    path("accounts/sign-up/", signup.signup_view, name="custom_account_signup"),
    path("accounts/sign-up/sent/", signup.signup_sent_view, name="signup_sent"),
    path("accounts/sign-up/change-email/", signup.signup_change_email_view, name="signup_change_email"),
    path("accounts/sign-up/complete/<str:token>/", signup.signup_complete_view, name="signup_complete"),
    path("accounts/", include("allauth.urls")),
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
    path("staff/", pipeline_views.dashboard_view, name="staff"),
    path("staff/flows/", pipeline_views.flows_view, name="staff_flows"),
    path("staff/", include("pipeline.urls")),
    path("staff/people/", people.people_view, name="staff_people"),
    path("staff/people/<int:user_pk>/", people.person_view, name="staff_person"),
    path("staff/stuck-signups/", stuck_signups.stuck_signups_view, name="stuck_signups"),
    path("staff/people/<int:user_pk>/service-doc/", userprofile_views.service_doc_view, name="service_doc"),
    path(
        "staff/stuck-signups/<str:kind>/<int:pk>/<str:action>/",
        stuck_signups.stuck_signup_action_view,
        name="stuck_signup_action",
    ),
    path("userprofile/", include("userprofile.urls")),
    path("cold_apply/", include("cold_apply.urls")),
    path("resume/", include("resume.urls")),
    path("releases/", include("releases.urls")),
    path("rates/", include("rates.urls")),
    # path("hlagents/", include("hlagents.urls")),
] + static(
    settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
)  # this only works in development

if settings.DEBUG:
    urlpatterns += [
        path("__debug__/", include("debug_toolbar.urls")),
        path("__reload__/", include("django_browser_reload.urls")),
    ]
