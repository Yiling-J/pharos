from unittest import TestCase, mock
from pharos.client import Client


class ClientTestCase(TestCase):
    @mock.patch("pharos.client.kubernetes")
    def test_client_with_settings(self, k8s_mock):
        client = Client("test", disable_compress=True)
        self.assertEqual(client.settings.disable_compress, True)
