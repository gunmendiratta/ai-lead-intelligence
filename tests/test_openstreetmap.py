import unittest
from unittest.mock import Mock, patch

from lead_intelligence.openstreetmap import OpenStreetMap


class OpenStreetMapTests(unittest.TestCase):
    @patch("lead_intelligence.openstreetmap.OpenStreetMap.session", create=True)
    def test_normalizes_nominatim_results(self, _session):
        provider = OpenStreetMap()
        response = Mock()
        response.json.return_value = [{
            "name": "Cafe Example",
            "display_name": "Cafe Example, Zurich, Switzerland",
            "osm_type": "node",
            "osm_id": 42,
            "type": "cafe",
            "address": {"city": "Zurich", "postcode": "8001"},
        }]
        provider.session.get = Mock(return_value=response)
        records = provider.search("Cafe Example", "Zurich")
        self.assertEqual(records[0]["business_name"], "Cafe Example")
        self.assertEqual(records[0]["postal_code"], "8001")
        self.assertIn("openstreetmap.org", records[0]["source_url"])


if __name__ == "__main__":
    unittest.main()