from django.contrib import admin

# Register your models here.
from .models import Participant, Interaction, Job


class ParticipantAdmin(admin.ModelAdmin):
    list_display = (
    'name', 'email', 'phone', 'veteran', 'active', 'current_phase', 'created_at', 'created_by', 'updated_at',
    'updated_by')
    list_filter = (
    'name', 'email', 'phone', 'veteran', 'active', 'current_phase', 'created_at', 'created_by', 'updated_at',
    'updated_by')
    search_fields = (
    'name', 'email', 'phone', 'veteran', 'active', 'current_phase', 'created_at', 'created_by', 'updated_at',
    'updated_by')


class InteractionAdmin(admin.ModelAdmin):
    list_display = ('user', 'participant', 'interaction_type', 'notes', 'created_at', 'updated_at')
    list_filter = ('user', 'participant', 'interaction_type', 'notes', 'created_at', 'updated_at')
    search_fields = ('user', 'participant', 'interaction_type', 'notes', 'created_at', 'updated_at')


class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'description', 'status', 'created_at', 'updated_at')
    list_filter = ('title', 'description', 'status', 'created_at', 'updated_at')
    search_fields = ('title', 'description', 'status', 'created_at', 'updated_at')


admin.site.register(Participant)
admin.site.register(Interaction)
admin.site.register(Job)
