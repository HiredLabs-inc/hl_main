import datetime

from django.test import TestCase

# Create your tests here.
# model tests
from django.test import TestCase
from cold_apply.models import Participant, Interaction, Job, Application, Phase, Step, KeywordAnalysis, \
    ParticipantExperience, \
    ParticipantOverview, WeightedBullet, BulletKeyword
from resume.models import Organization, Position, Experience, Overview, Bullet
from django.contrib.auth.models import User
from cold_apply.forms import ParticipantForm, InteractionForm, ExperienceForm


class ParticipantModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        test_user = User.objects.create_user(username='testuser', password='12345')
        Participant.objects.create(name='test', email='test@example.com', phone='1234567890',
                                   uploaded_resume_title='Test Resume', created_by=test_user, updated_by=test_user)

    def test_name_label(self):
        participant = Participant.objects.get(id=1)
        field_label = participant._meta.get_field('name').verbose_name
        self.assertEqual(field_label, 'name')

    def test_email_label(self):
        participant = Participant.objects.get(id=1)
        field_label = participant._meta.get_field('email').verbose_name
        self.assertEqual(field_label, 'email')

    def test_phone_label(self):
        participant = Participant.objects.get(id=1)
        field_label = participant._meta.get_field('phone').verbose_name
        self.assertEqual(field_label, 'phone')

    def test_dnc_label(self):
        participant = Participant.objects.get(id=1)
        field_label = participant._meta.get_field('dnc').verbose_name
        self.assertEqual(field_label, 'dnc')

    def test_uploaded_resume_label(self):
        participant = Participant.objects.get(id=1)
        field_label = participant._meta.get_field('uploaded_resume').verbose_name
        self.assertEqual(field_label, 'uploaded resume')

    def test_uploaded_resume_title_label(self):
        participant = Participant.objects.get(id=1)
        field_label = participant._meta.get_field('uploaded_resume_title').verbose_name
        self.assertEqual(field_label, 'uploaded resume title')

    def test_veteran_label(self):
        participant = Participant.objects.get(id=1)
        field_label = participant._meta.get_field('veteran').verbose_name
        self.assertEqual(field_label, 'veteran')

    def test_active_label(self):
        participant = Participant.objects.get(id=1)
        field_label = participant._meta.get_field('active').verbose_name
        self.assertEqual(field_label, 'active')

    def test_current_step_label(self):
        participant = Participant.objects.get(id=1)
        field_label = participant._meta.get_field('current_step').verbose_name
        self.assertEqual(field_label, 'current step')

    def test_created_at_label(self):
        participant = Participant.objects.get(id=1)
        field_label = participant._meta.get_field('created_at').verbose_name
        self.assertEqual(field_label, 'created at')

    def test_created_by_label(self):
        participant = Participant.objects.get(id=1)
        field_label = participant._meta.get_field('created_by').verbose_name
        self.assertEqual(field_label, 'created by')

    def test_updated_at_label(self):
        participant = Participant.objects.get(id=1)
        field_label = participant._meta.get_field('updated_at').verbose_name
        self.assertEqual(field_label, 'updated at')

    def test_updated_by_label(self):
        participant = Participant.objects.get(id=1)
        field_label = participant._meta.get_field('updated_by').verbose_name
        self.assertEqual(field_label, 'updated by')

    def test_object_name_is_name_colon_email(self):
        participant = Participant.objects.get(id=1)
        expected_object_name = f'{participant.name}: {participant.email}'
        self.assertEqual(expected_object_name, str(participant))


class JobModelTest(TestCase):

    def setUp(self):
        self.organization = Organization.objects.create(name='Test Organization')
        self.participant = Participant.objects.create(name='Test Participant')
        self.position = Position.objects.create(title='Test Position')
        self.user = User.objects.create(username='Test User')

        self.job = Job.objects.create(
            company=self.organization,
            participant=self.participant,
            title=self.position,
            description='Test job description',
            status='Open',
            status_reason='In Progress',
            application_link='https://example.com',
            created_by=self.user,
            updated_by=self.user,
        )

    def test_job_str(self):
        self.assertEqual(str(self.job),
                         f'{self.organization}: {self.position}, {self.job.status}: {self.participant.name}')

    def test_job_defaults(self):
        job = Job.objects.create(
            company=self.organization,
            participant=self.participant,
            title=self.position,
            description='Test job description',
        )

        self.assertEqual(job.status, 'Open')
        self.assertIsNone(job.status_reason)
        self.assertIsNone(job.application_link)
        self.assertIsNotNone(job.created_at)
        self.assertIsNone(job.created_by)
        self.assertIsNotNone(job.updated_at)
        self.assertIsNone(job.updated_by)


class PhaseModelTestCase(TestCase):
    def setUp(self):
        self.phase1 = Phase.objects.create(title='Phase 1', start='2022-01-01', end='2022-01-31', result='Pass',
                                           order=1)
        self.phase2 = Phase.objects.create(title='Phase 2', start='2022-02-01', end='2022-02-28', result='Fail',
                                           order=2)

    def test_phase_title(self):
        self.assertEqual(str(self.phase1), 'Phase 1')

    def test_phase_order(self):
        self.assertEqual(self.phase1.order, 1)
        self.assertEqual(self.phase2.order, 2)

    def test_phase_active_default(self):
        self.assertTrue(self.phase1.active)

    def test_phase_result_max_length(self):
        max_length = self.phase1._meta.get_field('result').max_length
        self.assertEqual(max_length, 200)


class StepTestCase(TestCase):
    def setUp(self):
        self.phase = Phase.objects.create(title='Test Phase', start='2023-04-01', end='2023-04-30', result='Pass')
        self.step = Step.objects.create(title='Test Step', description='Test Description', phase=self.phase, order=1,
                                        owner='Hired Labs')

    def test_step_creation(self):
        self.assertTrue(isinstance(self.step, Step))
        self.assertEqual(self.step.__str__(), 'Test Step: Test Phase')

    def test_step_fields(self):
        self.assertEqual(self.step.title, 'Test Step')
        self.assertEqual(self.step.description, 'Test Description')
        self.assertEqual(self.step.phase, self.phase)
        self.assertEqual(self.step.order, 1)
        self.assertEqual(self.step.owner, 'Hired Labs')

    def test_step_update(self):
        self.step.title = 'Updated Test Step'
        self.step.save()
        self.assertEqual(self.step.title, 'Updated Test Step')

    def test_step_deletion(self):
        self.step.delete()
        self.assertFalse(Step.objects.filter(title='Test Step').exists())


class ParticipantExperienceTestCase(TestCase):

    def setUp(self):
        self.org = Organization.objects.create(name='Test Organization')
        self.pos = Position.objects.create(title='Test Position')
        self.participant = Participant.objects.create(
            name='Test Participant',
            email='test@test.com',
            phone='1234567890',
            veteran=True,
            dnc=False,
            uploaded_resume='test_resume.pdf',
            uploaded_resume_title='Test Resume'
        )
        self.experience = Experience.objects.create(
            position=self.pos,
            org=self.org,
            start_date=datetime.date(2022, 1, 1),
            end_date=datetime.date(2022, 2, 1)
        )

    def test_participant_experience_string_representation(self):
        participant_experience = ParticipantExperience.objects.create(
            participant=self.participant,
            experience=self.experience
        )
        self.assertEqual(
            str(participant_experience),
            f'{self.participant.name}: {self.experience.position.title}, {self.experience.org.name}'
        )

    def test_participant_experience_participant_deletion(self):
        ParticipantExperience.objects.create(
            participant=self.participant,
            experience=self.experience
        )
        self.participant.delete()
        self.assertEqual(ParticipantExperience.objects.count(), 0)


class ParticipantFormTest(TestCase):

    def test_participant_form_invalid(self):
        form_data = {'name': '', 'email': 'johndoe', 'phone': '123', 'veteran': 'not_a_boolean', 'dnc': 'not_a_boolean',
                     'uploaded_resume_title': '', 'current_step': 'not_an_integer'}
        form = ParticipantForm(data=form_data)
        self.assertFalse(form.is_valid())


class ExperienceFormTest(TestCase):

    def test_experience_form_invalid(self):
        form_data = {'position': '', 'org': '', 'start_date': '', 'end_date': ''}
        form = ExperienceForm(data=form_data)
        self.assertFalse(form.is_valid())
