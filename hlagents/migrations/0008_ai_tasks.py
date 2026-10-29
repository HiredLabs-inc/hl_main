"""AI tasks (docs/designs/completed/ai-tasks.md §3): single-shot provider calls such as writing a
resume overview, with a TaskCall per call for the daily cap. 0009 seeds them.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('hlagents', '0007_lead_quality'),
    ]

    operations = [
        migrations.AddField(
            model_name='providerconfig',
            name='location',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AlterField(
            model_name='providerconfig',
            name='kind',
            field=models.CharField(choices=[('ollama', 'Ollama'), ('gemini', 'Gemini on Vertex AI')], max_length=20),
        ),
        migrations.CreateModel(
            name='TaskConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('key', models.CharField(choices=[('resume_overview', 'Resume overview'), ('resume_bullets', 'Resume bullet points'), ('bullet_rewrite', 'Bullet rewrite for a job')], max_length=50, unique=True)),
                ('model', models.CharField(max_length=100)),
                ('instructions', models.TextField()),
                ('options', models.JSONField(blank=True, default=dict)),
                ('active', models.BooleanField(default=True)),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='tasks', to='hlagents.providerconfig')),
            ],
            options={
                'ordering': ['key'],
            },
        ),
        migrations.CreateModel(
            name='TaskCall',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model', models.CharField(max_length=100)),
                ('input_tokens', models.PositiveIntegerField(default=0)),
                ('output_tokens', models.PositiveIntegerField(default=0)),
                ('cost', models.DecimalField(decimal_places=4, default=0, max_digits=10)),
                ('ok', models.BooleanField(default=True)),
                ('error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('config', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='calls', to='hlagents.taskconfig')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
