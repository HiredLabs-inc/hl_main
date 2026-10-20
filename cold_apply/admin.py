from django.contrib import admin

# Register your models here.
from .models import (
    BulletKeyword,
    Job,
    KeywordAnalysis,
    Location,
    Participant,
    Skill,
    State,
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
    list_display = ("user", "active", "created_at", "updated_at")
    list_filter = ("active", "created_at")
    search_fields = ("user__email", "user__first_name", "user__last_name")


class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "status", "created_at", "participant")
    list_filter = ("title", "company", "status", "created_at", "participant")
    search_fields = ("title", "company", "status", "created_at", "participant")


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
admin.site.register(Participant, ParticipantAdmin)
admin.site.register(Job, JobAdmin)
