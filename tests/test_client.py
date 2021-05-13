from unittest import TestCase, mock
from pharos.client import Client


class ClientTestCase(TestCase):
    @mock.patch("pharos.client.kubernetes")
    def test_client_with_settings(self, k8s_mock):
        client = Client("test", disable_compress=True)
        self.assertEqual(client.settings.disable_compress, True)

    @mock.patch("pharos.client.kubernetes")
    def test_change_context(self, k8s_mock):
        client = Client("test", context="foo")
        client.use_context("bar")
        expected_calls = [
            mock.call.new_client_from_config("test", context="foo"),
            mock.call.new_client_from_config("test", context="bar"),
        ]
        self.assertEqual(k8s_mock.config.method_calls, expected_calls)
