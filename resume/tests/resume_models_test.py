from django.test import TestCase
from datetime import date

from resume.models import Overview, Position, Organization, Degree, Concentration, Experience, Bullet, Education, \
    CertProjectActivity


# Create your tests here.

class TestOverview(TestCase):
    def setUp(self):
        self.position = Position.objects.create(title="Software Engineer")
        self.overview = Overview.objects.create(text="Job overview text", title=self.position)

    def test_str_method(self):
        self.assertEqual(str(self.overview), self.position.title)


class OrganizationModelTest(TestCase):
    def test_org_creation(self):
        org = Organization.objects.create(
            org_type='Work',
            name='Acme Corporation',
            website='https://www.acme.com'
        )
        self.assertEqual(org.name, 'Acme Corporation')
        self.assertEqual(org.org_type, 'Work')
        self.assertEqual(org.website, 'https://www.acme.com')


class PositionTest(TestCase):
    def test_position_string_representation(self):
        position = Position(title='Software Engineer')
        self.assertEqual(str(position), 'Software Engineer')


class DegreeModelTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Create a Degree object for use in the tests
        degree = Degree.objects.create(
            name='Bachelor of Science',
            abbr='BSc'
        )

    def test_name_label(self):
        degree = Degree.objects.get(id=1)
        field_label = degree._meta.get_field('name').verbose_name
        self.assertEqual(field_label, 'name')

    def test_abbr_label(self):
        degree = Degree.objects.get(id=1)
        field_label = degree._meta.get_field('abbr').verbose_name
        self.assertEqual(field_label, 'abbr')

    def test_name_max_length(self):
        degree = Degree.objects.get(id=1)
        max_length = degree._meta.get_field('name').max_length
        self.assertEqual(max_length, 250)

    def test_abbr_max_length(self):
        degree = Degree.objects.get(id=1)
        max_length = degree._meta.get_field('abbr').max_length
        self.assertEqual(max_length, 4)

    def test_object_name_is_abbr_name(self):
        degree = Degree.objects.get(id=1)
        expected_object_name = f'{degree.abbr}: {degree.name}'
        self.assertEqual(expected_object_name, str(degree))

class ConcentrationTestCase(TestCase):
    def setUp(self):
        Concentration.objects.create(name='Computer Science')

    def test_concentration_name(self):
        concentration = Concentration.objects.get(name='Computer Science')
        self.assertEqual(concentration.name, 'Computer Science')


class TestExperienceModel(TestCase):

    def test_string_representation(self):
        org = Organization.objects.create(name='Test Org', website='https://test.org')
        position = Position.objects.create(title='Test Position')
        start_date = date.today()
        experience = Experience.objects.create(org=org, position=position, start_date=start_date)
        self.assertEqual(str(experience), f'{org}: {position}, {start_date} - None')

class TestBullet(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Test Org')
        self.pos = Position.objects.create(title='Test Pos')
        self.exp = Experience.objects.create(
            start_date='2022-01-01', org=self.org, position=self.pos
        )
        self.bullet = Bullet.objects.create(
            experience=self.exp, text='Test bullet', type='Work'
        )

    def test_str_method(self):
        self.assertEqual(
            str(self.bullet),
            '{}: {}, {}'.format(self.bullet.id, self.bullet.text, self.bullet.experience)
        )

    def test_text_field(self):
        field_label = self.bullet._meta.get_field('text').verbose_name
        max_length = self.bullet._meta.get_field('text').max_length
        self.assertEqual(field_label, 'text')

    def test_type_field(self):
        field_label = self.bullet._meta.get_field('type').verbose_name
        max_length = self.bullet._meta.get_field('type').max_length
        self.assertEqual(field_label, 'type')
        self.assertEqual(max_length, 20)

    def test_experience_relation(self):
        related_model = self.bullet._meta.get_field('experience').related_model
        self.assertEqual(related_model, Experience)

    def test_type_choices(self):
        choices = self.bullet._meta.get_field('type').choices
        self.assertEqual(choices, [('Work', 'Work'), ('Summary', 'Summary')])


class TestEducationModel(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='test org')
        self.degree = Degree.objects.create(name='test degree', abbr='td')
        self.concentration = Concentration.objects.create(name='test concentration')
        self.education = Education.objects.create(org=self.org, degree=self.degree, concentration=self.concentration)

    def test_education_str(self):
        expected = f'{self.org}: {self.degree}, {self.concentration}'
        self.assertEqual(str(self.education), expected)

    def tearDown(self):
        self.org.delete()
        self.degree.delete()
        self.concentration.delete()
        self.education.delete()

class TestCertProjectActivity(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Test Organization')
        self.cert_proj_act = CertProjectActivity.objects.create(
            org=self.org,
            title='Test Title',
            description='Test Description',
            variety='Certification'
        )

    def test_str_method(self):
        self.assertEqual(str(self.cert_proj_act), 'Test Organization: Test Title, Test Description')

