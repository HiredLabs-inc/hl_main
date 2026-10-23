"""Who may see and work which flows on the dashboard. Staff work every flow;
anyone with work_lead_flows (volunteers in the Agents group) works the lead
flows, Funding and Outreach (docs/volunteer-logins.md §3.3)."""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import Enrollment, Flow

LEAD_FLOWS_PERMISSION = "pipeline.work_lead_flows"


def can_work_lead_flows(user):
    return user.is_staff or user.has_perm(LEAD_FLOWS_PERMISSION)


def can_work_flow(user, flow):
    if user.is_staff:
        return True
    return flow.subject == Flow.Subject.LEAD and user.has_perm(LEAD_FLOWS_PERMISSION)


def can_be_assigned(user, flow):
    """Active staff, and in a lead flow active users with work_lead_flows"""
    return user.is_active and can_work_flow(user, flow)


def lead_workers_q():
    """Users holding work_lead_flows through a group or directly (not superusers)"""
    app_label, codename = LEAD_FLOWS_PERMISSION.split(".")
    return Q(groups__permissions__codename=codename, groups__permissions__content_type__app_label=app_label) | Q(
        user_permissions__codename=codename, user_permissions__content_type__app_label=app_label
    )


def lead_flows_required(view):
    """Staff, or users with work_lead_flows: anonymous users are sent to login,
    everyone else gets a 403. The view still checks which flows they may see."""

    @wraps(view)
    def decorator(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not can_work_lead_flows(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return decorator


def enrollment_worker_required(view):
    """For views taking enrollment_pk: staff, or users who may work the
    enrollment's flow. Anyone else gets a 403, also for a missing enrollment."""

    @wraps(view)
    def decorator(request, enrollment_pk, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            enrollment = Enrollment.objects.select_related("flow").filter(pk=enrollment_pk).first()
            if enrollment is None or not can_work_flow(request.user, enrollment.flow):
                raise PermissionDenied
        return view(request, enrollment_pk, *args, **kwargs)

    return decorator
