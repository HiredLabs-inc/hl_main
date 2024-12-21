from django.contrib import admin

from .models import Profile, ServicePackage, VeteranProfile, Comment

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
        "state",
        "city",
        "is_veteran",
        "is_onboarded",
        "veteran_verified",
        "bootcamp",
        "dnc"
        )
    list_filter = (
        "user",
        "state",
        "city",
        "is_veteran",
        "veteran_verified",
        "is_onboarded",
        "bootcamp",
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
        "bootcamp",
        "dnc"
        )

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

admin.site.register(Comment, CommentAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(ServicePackage, ServicePackageAdmin)
admin.site.register(VeteranProfile, VeteranProfileAdmin)
