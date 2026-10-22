from functools import wraps

from allauth.account.utils import has_verified_email
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
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


def staff_required(view):
    """Decorator for staff-only views: anonymous users are sent to login,
    logged-in non-staff users get a 403"""

    @wraps(view)
    def decorator(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return decorator


VETERAN_REVIEW_PERMISSION = "userprofile.review_veteran_status"


def can_review_veteran_status(user):
    """Only staff holding review_veteran_status (or superusers) may open DD214s
    and change veteran status"""
    return user.is_staff and user.has_perm(VETERAN_REVIEW_PERMISSION)


def veteran_reviewer_required(view):
    """Decorator for views that expose service documents or change veteran
    status: anonymous users are sent to login, everyone else without the
    permission gets a 403"""

    @wraps(view)
    def decorator(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not can_review_veteran_status(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return decorator


class StaffRequiredMixin(UserPassesTestMixin):
    """CBV version of staff_required"""

    def test_func(self):
        return self.request.user.is_staff


def app_permission_required(app_label):
    """Decorator for views gated by any permission in a Django app, the same check
    as {% if perms.<app_label> %}: anonymous users are sent to login, logged-in
    users without the permission get a 403"""

    def wrapper(view):
        @wraps(view)
        def decorator(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not request.user.has_module_perms(app_label):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return decorator

    return wrapper


class AppPermissionRequiredMixin(UserPassesTestMixin):
    """CBV version of app_permission_required; set app_label on the view"""

    app_label: str = None

    def test_func(self):
        return self.request.user.has_module_perms(self.app_label)
