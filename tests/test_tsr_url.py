from unittest import TestCase

from exceptions import InvalidURL
from TSRUrl import TSRUrl


class TSRUrlValidationTests(TestCase):
    def test_accepts_official_tsr_item_url(self):
        url = TSRUrl("https://www.thesimsresource.com/downloads/details/id/123")

        self.assertEqual(url.itemId, 123)

    def test_rejects_lookalike_host_before_any_network_request(self):
        with self.assertRaises(InvalidURL):
            TSRUrl("https://evilthesimsresource.com/downloads/details/id/123")
