from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test.client import Client
import unittest

client = Client()
client.user = User.objects.create_user('john', 'lennon@thebeatles.com', 'johnpassword')
client.login(username='john', password='johnpassword')

class LoginTestCase(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('john', 'lennon@thebeatles.com', 'johnpassword')

    def testLogin(self):
        response = client.get(reverse('initLayersLayout'))
        self.assertEqual(response.status_code, 200)


