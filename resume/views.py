from django.shortcuts import render, redirect

from .models import *


# Create your views here.
def index(request):
    overview = Overview.objects.all().filter(title='Program Manager').values()
    orgs = Organization.objects.all().order_by('-chronological_order')
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
        'skills': skills
    }
    return render(request, 'resume/index.html', context)
