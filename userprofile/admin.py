from django.contrib import admin

from .guards import can_review_veteran_status
from .models import BootCampSession, Comment, Profile, ServicePackage, VeteranProfile

USER_SEARCH_FIELDS = ("user__email", "user__first_name", "user__last_name")


class ServiceDocHiddenMixin:
    """The admin form links service_doc straight to the file, so only veteran
    reviewers get the field"""

    def get_exclude(self, request, obj=None):
        exclude = list(super().get_exclude(request, obj) or [])
        if not can_review_veteran_status(request.user):
            exclude.append("service_doc")
        return exclude


class VeteranProfileAdmin(ServiceDocHiddenMixin, admin.ModelAdmin):
    list_display = (
        "user",
        "service_branch",
    )
    list_filter = (
        "service_branch",
    )
    search_fields = USER_SEARCH_FIELDS

class ProfileAdmin(ServiceDocHiddenMixin, admin.ModelAdmin):
    list_display = (
        "user",
        "state",
        "city",
        "is_veteran",
        "is_onboarded",
        "veteran_verified",
        "bootcamp",
        "dnc"
        )
    list_filter = (
        "state",
        "city",
        "is_veteran",
        "veteran_verified",
        "is_onboarded",
        "bootcamp",
        "dnc"
        )
    search_fields = USER_SEARCH_FIELDS + ("city", "state")

class ServicePackageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
    )
    list_filter = (
        "name",
    )
    search_fields = (
        "name",
    )

class CommentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
    )
    list_filter = (
        "name",
        "email",
    )
    search_fields = (
        "name",
        "email",
    )

class BootCampSessionAdmin(admin.ModelAdmin):
    list_display = ("start_date", "created_at")
    ordering = ("-start_date",)

admin.site.register(BootCampSession, BootCampSessionAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(ServicePackage, ServicePackageAdmin)
admin.site.register(VeteranProfile, VeteranProfileAdmin)
