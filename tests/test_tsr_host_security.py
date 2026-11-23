"""Strict host validation applies to every console clipboard link."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from TSRUrl import TSRUrl
from exceptions import InvalidURL


class TSRHostTests(unittest.TestCase):
    def test_accepts_official_https(self):
        self.assertEqual(TSRUrl("https://www.thesimsresource.com/downloads/details/id/123").itemId, 123)
        self.assertEqual(TSRUrl("https://thesimsresource.com/downloads/321").itemId, 321)

    def test_rejects_bad_hosts_and_schemes(self):
        for url in (
            "https://evilthesimsresource.com/downloads/details/id/123",
            "https://www.thesimsresource.com.evil.example/downloads/details/id/123",
            "http://www.thesimsresource.com/downloads/details/id/123",
            "https://user:pass@www.thesimsresource.com/downloads/details/id/123",
            "file:///downloads/details/id/123",
            "https://www.thesimsresource.com:444/downloads/details/id/123",
            "https://[invalid/downloads/details/id/123",
        ):
            with self.subTest(url=url), self.assertRaises(InvalidURL):
                TSRUrl(url)


if __name__ == "__main__":
    unittest.main()
