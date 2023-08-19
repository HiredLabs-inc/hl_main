from django.contrib import admin

# Register your models here.
from .models import (
    BulletKeyword,
    Interaction,
    Job,
    KeywordAnalysis,
    Location,
    Participant,
    Phase,
    Skill,
    State,
    Step,
    WeightedBullet,
)


class StateAdmin(admin.ModelAdmin):
    list_display = ("name", "abbreviation")
    list_filter = ("name", "abbreviation")
    search_fields = ("name", "abbreviation")


class BulletKeywordAdmin(admin.ModelAdmin):
    list_display = ("bullet", "unigram", "bigram", "trigram")
    list_filter = ("bullet", "unigram", "bigram", "trigram")
    search_fields = ("bullet", "unigram", "bigram", "trigram")


class WeightedBulletAdmin(admin.ModelAdmin):
    list_display = ("participant", "position", "bullet", "weight")
    list_filter = ("participant", "position", "bullet", "weight")
    search_fields = ("participant", "position", "bullet", "weight")


class ParticipantAdmin(admin.ModelAdmin):
    list_display = (
        "active",
        "current_step",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "active",
        "current_step",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "active",
        "current_step",
        "created_at",
        "updated_at",
    )


class InteractionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "participant",
        "interaction_type",
        "notes",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "user",
        "participant",
        "interaction_type",
        "notes",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "user",
        "participant",
        "interaction_type",
        "notes",
        "created_at",
        "updated_at",
    )


class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "status", "created_at", "participant")
    list_filter = ("title", "company", "status", "created_at", "participant")
    search_fields = ("title", "company", "status", "created_at", "participant")


class PhaseAdmin(admin.ModelAdmin):
    list_display = ("title", "order")
    list_filter = ("title", "order")
    search_fields = ("title", "order")


class StepAdmin(admin.ModelAdmin):
    list_display = ("title", "description", "order", "phase")
    list_filter = ("title", "description", "order", "phase")
    search_fields = ("title", "description", "order", "phase")


class KeywordAnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "unigram", "bigram", "trigram")
    list_filter = ("job", "unigram", "bigram", "trigram")
    search_fields = ("job", "unigram", "bigram", "trigram")


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    pass


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    pass


admin.site.register(State, StateAdmin)
admin.site.register(BulletKeyword, BulletKeywordAdmin)
admin.site.register(WeightedBullet, WeightedBulletAdmin)
admin.site.register(KeywordAnalysis, KeywordAnalysisAdmin)
admin.site.register(Phase, PhaseAdmin)
admin.site.register(Step, StepAdmin)
admin.site.register(Participant, ParticipantAdmin)
admin.site.register(Interaction, InteractionAdmin)
admin.site.register(Job, JobAdmin)
