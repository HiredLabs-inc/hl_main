from django.contrib import admin

# Register your models here.
from .models import Participant, Interaction, Job, Phase, Step, KeywordAnalysis


class ParticipantAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'email', 'phone', 'veteran', 'active', 'current_step', 'created_at', 'created_by', 'updated_at',
        'updated_by')
    list_filter = (
        'name', 'email', 'phone', 'veteran', 'active', 'current_step', 'created_at', 'created_by', 'updated_at',
        'updated_by')
    search_fields = (
        'name', 'email', 'phone', 'veteran', 'active', 'current_step', 'created_at', 'created_by', 'updated_at',
        'updated_by')


class InteractionAdmin(admin.ModelAdmin):
    list_display = ('user', 'participant', 'interaction_type', 'notes', 'created_at', 'updated_at')
    list_filter = ('user', 'participant', 'interaction_type', 'notes', 'created_at', 'updated_at')
    search_fields = ('user', 'participant', 'interaction_type', 'notes', 'created_at', 'updated_at')


class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'status', 'created_at', 'participant')
    list_filter = ('title', 'company', 'status', 'created_at', 'participant')
    search_fields = ('title', 'company', 'status', 'created_at', 'participant')


class PhaseAdmin(admin.ModelAdmin):
    list_display = ('title', 'order')
    list_filter = ('title', 'order')
    search_fields = ('title', 'order')


class StepAdmin(admin.ModelAdmin):
    list_display = ('title', 'description', 'order', 'phase')
    list_filter = ('title', 'description', 'order', 'phase')
    search_fields = ('title', 'description', 'order', 'phase')


class KeywordAnalysisAdmin(admin.ModelAdmin):
    list_display = ('job', 'unigram', 'bigram', 'trigram')
    list_filter = ('job', 'unigram', 'bigram', 'trigram')
    search_fields = ('job', 'unigram', 'bigram', 'trigram')


admin.site.register(KeywordAnalysis, KeywordAnalysisAdmin)
admin.site.register(Phase, PhaseAdmin)
admin.site.register(Step, StepAdmin)
admin.site.register(Participant, ParticipantAdmin)
admin.site.register(Interaction, InteractionAdmin)
admin.site.register(Job, JobAdmin)
