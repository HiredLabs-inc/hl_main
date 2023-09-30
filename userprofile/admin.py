from django.contrib import admin

from .models import Profile, ServicePackage, VeteranProfile

class VeteranProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "service_branch",
    )
    list_filter = (
        "user",
        "service_branch",
    )
    search_fields = (
        "user",
        "service_branch"
    )

class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "nickname",
        "state",
        "city",
        "is_veteran",
        "is_onboarded",
        "veteran_verified",
        "service_branch",
        "dnc"
        )
    list_filter = (
        "user",
        "nickname",
        "state",
        "city",
        "is_veteran",
        "veteran_verified",
        "is_onboarded",
        "service_branch",
        "dnc"
        )
    search_fields = (
        "user",
        "nickname",
        "state",
        "city",
        "is_veteran",
        "veteran_verified",
        "is_onboarded",
        "service_branch",
        "dnc"
        )

admin.site.register(Profile)
admin.site.register(ServicePackage)
admin.site.register(VeteranProfile)
