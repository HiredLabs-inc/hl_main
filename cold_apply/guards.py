from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404

from .models import Participant


def owned_by(queryset, user, owner_lookup):
    """Restrict a queryset to rows the user may see: staff see everything,
    participants only rows that belong to them. owner_lookup is the path from
    the model to its owning User, e.g. "participant__user"."""
    if user.is_staff:
        return queryset
    return queryset.filter(**{owner_lookup: user})


def can_access_participant(user, participant_id):
    return user.is_staff or Participant.objects.filter(pk=participant_id, user=user).exists()


class OwnedObjectMixin(LoginRequiredMixin):
    """For detail/update/delete views: objects the user doesn't own 404"""

    owner_lookup = None

    def get_queryset(self):
        return owned_by(super().get_queryset(), self.request.user, self.owner_lookup)


class ParticipantAccessMixin(LoginRequiredMixin):
    """For views scoped by a participant pk in the URL (the "pk" kwarg)"""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_access_participant(request.user, kwargs["pk"]):
            raise Http404
        return super().dispatch(request, *args, **kwargs)


class ParticipantOrStaffMixin(LoginRequiredMixin):
    """For pages any participant may use, but not a signup with no Participant yet"""

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and not (user.is_staff or Participant.objects.filter(user=user).exists()):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
