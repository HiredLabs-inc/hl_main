from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import DetailView, ListView

from .models import Overview, Organization, Experience, Bullet, Education, CertProjectActivity, LanguageFATS, Position


# Create your views here.
def index(request, pk):
    overview = Overview.objects.all()
    orgs = Organization.objects.all()
    work = Experience.objects.all().order_by('-start_date')
    bullets = Bullet.objects.all()
    edu = Education.objects.all()
    certs = CertProjectActivity.objects.all().filter(variety='Certification')
    projects = CertProjectActivity.objects.all().filter(variety='Project')
    activities = CertProjectActivity.objects.all().filter(variety='Activity')
    hlangs = LanguageFATS.objects.all().filter(lang_type='Human')
    clangs = LanguageFATS.objects.all().filter(lang_type='Computer')
    frameworks = LanguageFATS.objects.all().filter(lang_type='Framework')
    abilities = LanguageFATS.objects.all().filter(lang_type='Ability')
    technologies = LanguageFATS.objects.all().filter(lang_type='Technology')
    skills = LanguageFATS.objects.all().filter(lang_type='Skill')
    target = Position.objects.all().filter(id=pk)

    context = {
        'overview': overview,
        'orgs': orgs,
        'work': work,
        'bullets': bullets,
        'edu': edu,
        'certs': certs,
        'projects': projects,
        'activities': activities,
        'hlangs': hlangs,
        'clangs': clangs,
        'frameworks': frameworks,
        'abilities': abilities,
        'technologies': technologies,
        'skills': skills,
        'target': target,
    }
    return render(request, 'resume/index.html', context)


