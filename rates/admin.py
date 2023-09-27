from django.contrib import admin

from .models import RateRequest, RateResponse, Skill, Country


class RateRequestAdmin(admin.ModelAdmin):
    list_display = ('skill', 'level', 'employer_country', 'worker_country', 'rate', 'time_stamp')
    list_filter = ('skill', 'level', 'employer_country', 'worker_country', 'rate', 'time_stamp')
    search_fields = ('skill', 'level', 'employer_country', 'worker_country', 'rate', 'time_stamp')


class RateResponseAdmin(admin.ModelAdmin):
    list_display = ('rate_request', 'lowest_rate')
    list_filter = ('rate_request', 'lowest_rate')
    search_fields = ('rate_request', 'lowest_rate')


class SkillAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_filter = ('name',)
    search_fields = ('name',)


class CountryAdmin(admin.ModelAdmin):
    list_display = ('rank', 'name', 'zone')
    list_filter = ('rank', 'name', 'zone')
    search_fields = ('rank', 'name', 'zone')


admin.site.register(RateRequest, RateRequestAdmin)
admin.site.register(RateResponse, RateResponseAdmin)
admin.site.register(Skill, SkillAdmin)
admin.site.register(Country, CountryAdmin)
