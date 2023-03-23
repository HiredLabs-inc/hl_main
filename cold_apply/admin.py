from django.contrib import admin

# Register your models here.
from .models import Participant, Interaction, Job, Phase, Step, KeywordAnalysis, ParticipantExperience, \
    ParticipantOverview, WeightedBullet, BulletKeyword


class BulletKeywordAdmin(admin.ModelAdmin):
    list_display = ('bullet', 'unigram', 'bigram', 'trigram')
    list_filter = ('bullet', 'unigram', 'bigram', 'trigram')
    search_fields = ('bullet', 'unigram', 'bigram', 'trigram')


class WeightedBulletAdmin(admin.ModelAdmin):
    list_display = ('participant', 'position', 'bullet', 'weight')
    list_filter = ('participant', 'position', 'bullet', 'weight')
    search_fields = ('participant', 'position', 'bullet', 'weight')


class ParticipantOverviewAdmin(admin.ModelAdmin):
    list_display = ('participant', 'overview')
    list_filter = ('participant', 'overview')
    search_fields = ('participant', 'overview')


class ParticipantExperienceAdmin(admin.ModelAdmin):
    list_display = ('participant', 'experience')
    list_filter = ('participant', 'experience')
    search_fields = ('participant', 'experience')


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
    list_display = ('id', 'job', 'unigram', 'bigram', 'trigram')
    list_filter = ('job', 'unigram', 'bigram', 'trigram')
    search_fields = ('job', 'unigram', 'bigram', 'trigram')


admin.site.register(BulletKeyword, BulletKeywordAdmin)
admin.site.register(WeightedBullet, WeightedBulletAdmin)
admin.site.register(ParticipantOverview, ParticipantOverviewAdmin)
admin.site.register(ParticipantExperience, ParticipantExperienceAdmin)
admin.site.register(KeywordAnalysis, KeywordAnalysisAdmin)
admin.site.register(Phase, PhaseAdmin)
admin.site.register(Step, StepAdmin)
admin.site.register(Participant, ParticipantAdmin)
admin.site.register(Interaction, InteractionAdmin)
admin.site.register(Job, JobAdmin)
