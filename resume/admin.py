from django.contrib import admin

from .models import Overview, Organization, Position, Degree, \
 Concentration, Experience, Bullet, Education, CertProjectActivity, \
 LanguageFATS


class ExperienceAdmin(admin.ModelAdmin):
    list_display = ('start_date', 'end_date', 'label', 'org', 'position')
    list_filter = ('label', 'org', 'position')
    search_fields = ('org', 'position')


class BulletAdmin(admin.ModelAdmin):
    list_display = ('experience', 'text', 'type')
    list_filter = ('experience', 'type')
    search_fields = ('experience', 'text')


class EducationAdmin(admin.ModelAdmin):
    list_display = ('org', 'degree', 'concentration')
    list_filter = ('org', 'degree', 'concentration')
    search_fields = ('org', 'degree', 'concentration')


class CertProjectActivityAdmin(admin.ModelAdmin):
    list_display = ('org', 'title', 'description', 'variety')
    list_filter = ('org', 'title', 'variety')
    search_fields = ('org', 'title', 'description')


class LanguageFATSAdmin(admin.ModelAdmin):
    list_display = ('name', 'proficiency')
    list_filter = ('name', 'proficiency')
    search_fields = ('name', 'proficiency')


class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'state', 'country')
    list_filter = ('name', 'city', 'state', 'country')
    search_fields = ('name', 'city', 'state', 'country')


class PositionAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_filter = ('name',)
    search_fields = ('name',)


class DegreeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_filter = ('name',)
    search_fields = ('name',)


class ConcentrationAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_filter = ('name',)
    search_fields = ('name',)


class OverviewAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone')
    list_filter = ('name', 'email', 'phone')
    search_fields = ('name', 'email', 'phone')


admin.site.register(Overview)
admin.site.register(Organization)
admin.site.register(Position)
admin.site.register(Degree)
admin.site.register(Concentration)
admin.site.register(Experience)
admin.site.register(Bullet)
admin.site.register(Education)
admin.site.register(CertProjectActivity)
admin.site.register(LanguageFATS)
