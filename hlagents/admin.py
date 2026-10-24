from django.contrib import admin

from .models import AgentConfig, AgentLimits, AgentRun, Lead, ProviderConfig, TaskCall, TaskConfig


@admin.register(ProviderConfig)
class ProviderConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "base_url", "location", "secret_env", "active")


@admin.register(AgentConfig)
class AgentConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "agent_type", "provider", "model", "active")
    list_filter = ("agent_type", "provider", "active")


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ("id", "config", "model", "status", "started_by", "iterations", "cost", "created_at")
    list_filter = ("status", "config")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("__str__", "kind", "source", "contact_email", "review_status", "opted_out_at", "created_at")
    list_filter = ("kind", "source", "review_status")
    search_fields = ("org_name", "first_name", "last_name", "contact_email")


@admin.register(TaskConfig)
class TaskConfigAdmin(admin.ModelAdmin):
    list_display = ("key", "provider", "model", "active")


@admin.register(TaskCall)
class TaskCallAdmin(admin.ModelAdmin):
    list_display = ("id", "config", "model", "user", "ok", "input_tokens", "output_tokens", "cost", "created_at")
    list_filter = ("config", "ok")
    readonly_fields = ("created_at",)


admin.site.register(AgentLimits)
