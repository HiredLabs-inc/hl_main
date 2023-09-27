from django.contrib import admin

# Register your models here.
from .models import App, Release, Note, Feedback


class AppAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description')
    list_filter = ('id','name',)


class NoteAdmin(admin.ModelAdmin):
    list_display = ('release', 'text')
    list_filter = ('release',)


class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'app', 'short_description', 'created')
    list_filter = ('user', 'app', 'created')


class ReleaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'app', 'major', 'minor', 'patch', 'date')
    list_filter = ('id', 'app', 'date')


admin.site.register(App, AppAdmin)
admin.site.register(Release, ReleaseAdmin)
admin.site.register(Note, NoteAdmin)
admin.site.register(Feedback, FeedbackAdmin)
