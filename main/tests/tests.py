from django.test import TestCase, Client
import vcr
from project_admin.models import ProjectConfiguration
from django.core.management import call_command
from django.conf import settings
from open_humans.models import OpenHumansMember


class LoginTestCase(TestCase):
    """
    Test the login logic of the OH API
    """

    def setUp(self):
        settings.DEBUG = True
        settings.OPENHUMANS_APP_BASE_URL = "http://127.0.0.1"
        call_command('init_proj_config')
        project_config = ProjectConfiguration.objects.get(id=1)
        project_config.oh_client_id = "6yNYmUlXN1wLwQFQR0lnUohR1KMeVt"
        project_config.oh_client_secret = "Y2xpZW50aWQ6Y2xpZW50c2VjcmV0"
        project_config.save()

    @vcr.use_cassette('main/tests/fixtures/vcr_cassettes/synopsis.yaml')
    def test_complete(self):
        c = Client()
        self.assertEqual(0,
                         OpenHumansMember.objects.all().count())
        response = c.get("/complete", {'code': 'mytestcode'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'main/complete.html')
        self.assertEqual(1,
                         OpenHumansMember.objects.all().count())
