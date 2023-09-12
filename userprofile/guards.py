from allauth.account.utils import has_verified_email
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect


def email_verified_test(request):
    """Runs passenger_test and then checks that the passenger is email verified,
    returning a tuple of (unauthorised_response, passenger), same mechanics as
    passenger_required_test"""
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path()), None

    if not has_verified_email(request.user):
        return redirect("account_verified_email_required"), None

    return None, request.user


def verified_required(view):
    """Decorator for views that checks that the user is logged in and is a passenger
    passes passenger as first arg to the view if passes test
    """

    def decorator(request, *args, **kwargs):
        unauthorised_response, user = email_verified_test(request)
        return unauthorised_response or view(request, *args, **kwargs)

    return decorator


class VerifiedRequiredMixin(UserPassesTestMixin):
    """CBV version on the passenger_required decorator"""

    unauthorised_response: HttpResponse = None

    def get_unauthorised_response(self) -> HttpResponse:
        unauthorised_response, _ = email_verified_test(self.request)
        return unauthorised_response

    def test_func(self):
        self.unauthorised_response = self.get_unauthorised_response()
        return self.unauthorised_response is None

    def handle_no_permission(self) -> HttpResponseRedirect:
        return self.unauthorised_response
