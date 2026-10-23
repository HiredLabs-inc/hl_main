from django.contrib import admin

from .models import Activity, Enrollment, Flow, Phase, Step


class PhaseInline(admin.TabularInline):
    model = Phase
    extra = 0
    fields = ("title", "order", "start", "end", "result")


class StepInline(admin.TabularInline):
    model = Step
    extra = 0
    fields = ("title", "order", "owner", "required_permission", "description")


@admin.register(Flow)
class FlowAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "active", "order")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [PhaseInline]


@admin.register(Phase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ("title", "flow", "order")
    list_filter = ("flow",)
    inlines = [StepInline]


@admin.register(Step)
class StepAdmin(admin.ModelAdmin):
    list_display = ("title", "phase", "order", "owner", "required_permission")
    list_filter = ("phase__flow", "owner")
    search_fields = ("title",)


# Enrollments and activity are changed through pipeline.services (the staff
# dashboard), which keeps the timeline complete, so admin is read-only.
class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Enrollment)
class EnrollmentAdmin(ReadOnlyAdmin):
    list_display = ("person", "flow", "current_step", "status", "assignee", "step_entered_at")
    list_filter = ("flow", "status")
    search_fields = ("person__email", "person__first_name", "person__last_name")


@admin.register(Activity)
class ActivityAdmin(ReadOnlyAdmin):
    list_display = ("person", "lead", "kind", "from_value", "to_value", "actor", "created_at")
    list_filter = ("kind",)
    search_fields = ("person__email", "person__first_name", "person__last_name", "lead__org_name", "lead__contact_email")
