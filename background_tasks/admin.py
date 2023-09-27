from django.contrib import admin

from background_tasks.models import Task


# Register your models here.



@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "target_path", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at", "updated_at")
    search_fields = ("target_path", "payload", "result")    