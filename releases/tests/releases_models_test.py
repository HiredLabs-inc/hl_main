from django.contrib.auth.models import User
from django.test import TestCase

from releases.models import App, Release, Note, Feedback


# Create your tests here.
class AppTestCase(TestCase):
    def setUp(self):
        self.app = App.objects.create(name='Test App', description='A test description')

    def test_app_name(self):
        self.assertEqual(self.app.name, 'Test App')

    def test_app_description(self):
        self.assertEqual(self.app.description, 'A test description')

class ReleaseModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.app = App.objects.create(name='testapp', description='test description')
        self.release = Release.objects.create(title='test release', author=self.user, app=self.app, major=1, minor=2, patch=3)

    def test_string_representation(self):
        self.assertEqual(str(self.release), '1.2.3')

class TestNote(TestCase):
    def setUp(self):
        self.release = Release.objects.create(
            title='Test Release', author=User.objects.create_user('user', password='test'),
            app=App.objects.create(name='Test App', description='Test description'),
            major=1, minor=0, patch=0
        )
        self.note = Note.objects.create(release=self.release, text='Test note text')

    def test_note_text(self):
        self.assertEqual(str(self.note), 'Test note text')


class TestFeedback(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'testpass')
        self.app = App.objects.create(name='Test App', description='Test description')
        self.feedback = Feedback.objects.create(
            user=self.user,
            app=self.app,
            short_description='Test feedback',
            text='Test feedback text',
            status='Unread'
        )

    def test_feedback_creation(self):
        self.assertEqual(self.feedback.user.username, 'testuser')
        self.assertEqual(self.feedback.app.name, 'Test App')
        self.assertEqual(self.feedback.short_description, 'Test feedback')
        self.assertEqual(self.feedback.text, 'Test feedback text')
        self.assertEqual(self.feedback.status, 'Unread')
