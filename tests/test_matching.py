import unittest

from lead_intelligence.matching import compare_businesses


class MatchingTests(unittest.TestCase):
    def test_same_address_with_abbreviation_is_verified(self):
        result = compare_businesses(
            {"name": "Alpine Residence", "address": "12 Main Street, St Moritz, 7500", "city": "St Moritz"},
            {"name": "Alpine Residence", "address": "12 Main St., St. Moritz 7500", "city": "St. Moritz"},
        )
        self.assertEqual(result.status, "Verified")
        self.assertGreaterEqual(result.address_similarity, 90)

    def test_same_name_different_address_requires_review(self):
        result = compare_businesses(
            {"name": "Sunset Apartments", "address": "1 Lake Road, Zurich 8001", "city": "Zurich"},
            {"name": "Sunset Apartments", "address": "44 Mountain Road, Geneva 1201", "city": "Geneva"},
        )
        self.assertEqual(result.status, "Rejected")

    def test_missing_candidate_information_is_not_verified(self):
        result = compare_businesses(
            {"name": "Cafe Example", "address": "1 Lake Road"},
            {"name": "", "address": ""},
        )
        self.assertEqual(result.status, "No Information Found")


if __name__ == "__main__":
    unittest.main()
