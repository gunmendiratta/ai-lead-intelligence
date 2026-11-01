import unittest

from lead_intelligence.commands import apply_command, parse_command


class CommandTests(unittest.TestCase):
    def test_excludes_managed_hotels(self):
        command = parse_command("Remove any hotel that is already managed by a company")
        kept, excluded = apply_command(
            [
                {"business_name": "Independent Hotel", "category": "hotel"},
                {"business_name": "Hotel Group Zurich", "category": "hotel", "management_company": "Acme Group"},
            ],
            command,
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(excluded), 1)

    def test_unknown_command_is_explicit(self):
        self.assertEqual(parse_command("find the best leads").action, "unknown")


if __name__ == "__main__":
    unittest.main()