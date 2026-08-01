import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'plugin.video.aiostreams'))

from resources.lib.safe_logging import error_name, redact_identifier  # noqa: E402


class SafeLoggingTests(unittest.TestCase):
    def test_identifier_is_stable_and_not_exposed(self):
        identifier = 'tt1375666'
        redacted = redact_identifier(identifier)

        self.assertEqual(redacted, redact_identifier(identifier))
        self.assertNotIn(identifier, redacted)
        self.assertTrue(redacted.startswith('id:'))

    def test_missing_identifier_and_error_name_are_safe(self):
        self.assertEqual('<missing>', redact_identifier(None))
        self.assertEqual('ValueError', error_name(ValueError('secret details')))


if __name__ == '__main__':
    unittest.main()
