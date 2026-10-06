import unittest
from unittest import mock

from sokuhou import http


class HttpTlsTest(unittest.TestCase):
    def test_legacy_tls_context_lowers_security_level_only_when_requested(self):
        fake_context = mock.Mock()
        with mock.patch("ssl.create_default_context", return_value=fake_context):
            self.assertIs(http._legacy_tls_context(), fake_context)
        fake_context.set_ciphers.assert_called_once_with("DEFAULT:@SECLEVEL=1")


if __name__ == "__main__":
    unittest.main()
