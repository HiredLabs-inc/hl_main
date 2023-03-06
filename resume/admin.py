from django.contrib import admin

from .models import Overview, Organization, Position, Degree,\
 Concentration, Experience, Bullet, Education, CertProjectActivity,\
 LanguageFATS

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
