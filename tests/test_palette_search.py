"""Regression tests for CreatorStudios Quick Switch filtering."""
import unittest

from palette_search import match_commands


COMMANDS = [
    {"title": "Dashboard", "description": "Overview and health", "keywords": "home"},
    {"title": "My Mod Library", "description": "Installed content", "keywords": "mods"},
    {"title": "Scan library", "description": "Refresh installed files", "keywords": "health duplicates"},
    {"title": "Discover", "description": "Browse Sims content", "keywords": "find downloads"},
]


class PaletteSearchTests(unittest.TestCase):
    def test_empty_query_keeps_navigation_order(self):
        self.assertEqual(match_commands(COMMANDS, "  "), COMMANDS)

    def test_search_uses_keywords_and_description(self):
        self.assertEqual(match_commands(COMMANDS, "health scan")[0]["title"], "Scan library")
        self.assertEqual(match_commands(COMMANDS, "find downloads")[0]["title"], "Discover")

    def test_case_insensitive_prefixes_rank_first(self):
        self.assertEqual(match_commands(COMMANDS, "LIBRARY")[0]["title"], "My Mod Library")

    def test_unrelated_search_returns_no_results(self):
        self.assertEqual(match_commands(COMMANDS, "uninstall everything"), [])

    def test_results_do_not_change_input(self):
        originals = list(COMMANDS)
        match_commands(COMMANDS, "content")
        self.assertEqual(COMMANDS, originals)


if __name__ == "__main__":
    unittest.main()
