from django.contrib.auth.models import User
from django.test import TestCase

from userprofile.models import Profile


# Create your tests here.
class ProfileTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.profile = Profile.objects.create(
            user=self.user,
            nickname='Testy McTestface'
        )

    def test_str_method(self):
        expected_str = f"{self.user.id}: {self.user.get_full_name()}, AKA: {self.profile.nickname}"
        self.assertEqual(str(self.profile), expected_str)

    def test_user_field(self):
        self.assertEqual(self.profile.user, self.user)

    def test_nickname_field(self):
        self.assertEqual(self.profile.nickname, 'Testy McTestface')
