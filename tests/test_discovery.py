import unittest

from bs4 import BeautifulSoup

from lead_intelligence.discovery import _heuristic_records, _jsonld_records, classify_source, google_maps_query
from lead_intelligence.extraction import safe_public_url
from lead_intelligence.templates import extract_template_records
from lead_intelligence.planner import create_plan


class DiscoveryTests(unittest.TestCase):
    def test_extracts_schema_business(self):
        soup = BeautifulSoup(
            '<script type="application/ld+json">{"@type":"LocalBusiness","name":"Cafe Example","address":{"streetAddress":"1 Lake Rd","addressLocality":"Zurich","postalCode":"8001"},"telephone":"+41 44 123 45 67"}</script>',
            "html.parser",
        )
        record = _jsonld_records(soup, "https://example.com")[0]
        self.assertEqual(record["business_name"], "Cafe Example")
        self.assertEqual(record["city"], "Zurich")

    def test_extracts_repeated_cards(self):
        soup = BeautifulSoup('<article class="listing-card"><h2>Lake Hotel</h2><div class="address">12 Lake Rd</div><a href="/lake">View</a></article>', "html.parser")
        record = _heuristic_records(soup, "https://example.com")[0]
        self.assertEqual(record["website"], "https://example.com/lake")

    def test_maps_url_is_classified_without_scraping(self):
        url = "https://www.google.com/maps/search/restaurants+in+zurich"
        self.assertEqual(classify_source(url), "google_maps")
        self.assertEqual(google_maps_query(url), "restaurants in zurich")

    def test_private_and_local_urls_are_blocked(self):
        self.assertFalse(safe_public_url("http://localhost:8501"))
        self.assertFalse(safe_public_url("http://127.0.0.1/admin"))
        self.assertFalse(safe_public_url("http://192.168.1.10/"))

    def test_urls_with_embedded_credentials_are_blocked(self):
        self.assertFalse(safe_public_url("https://user:password@example.com/"))

    def test_search_engine_urls_are_rejected_from_page_discovery(self):
        self.assertEqual(classify_source("https://www.bing.com/search?q=restaurants+zurich"), "search_engine")

    def test_booking_template_extracts_public_cards(self):
        soup = BeautifulSoup(
            '<div data-testid="property-card"><div data-testid="title">Lake Hotel</div><div data-testid="address">1 Lake Road</div><a data-testid="title-link" href="/hotel/lake">Open</a></div>',
            "html.parser",
        )
        records, domain = extract_template_records(soup, "https://www.booking.com/searchresults.html")
        self.assertEqual(domain, "booking.com")
        self.assertEqual(records[0]["business_name"], "Lake Hotel")
        self.assertEqual(records[0]["source_domain_template"], "booking.com")

    def test_plan_requests_all_fields_and_crawl_steps_without_prompt(self):
        plan = create_plan("https://example.com/directory", "")
        self.assertIn("email", plan.fields)
        self.assertIn("postal_code", plan.fields)
        self.assertTrue(any("scroll" in step.lower() for step in plan.execution_steps))
        self.assertTrue(any("google places" in step.lower() for step in plan.execution_steps))

    def test_booking_fallback_card_uses_hotel_link_name(self):
        soup = BeautifulSoup(
            '<li class="hotel-card"><a href="/hotel/ch/lake.html">Lake Hotel</a><div class="address">Zurich</div></li>',
            "html.parser",
        )
        records, _ = extract_template_records(soup, "https://www.booking.com/searchresults.html")
        self.assertEqual(records[0]["business_name"], "Lake Hotel")

    def test_booking_organization_metadata_is_not_a_hotel_lead(self):
        soup = BeautifulSoup(
            '<script type="application/ld+json">{"@type":"Organization","name":"Booking.com"}</script>',
            "html.parser",
        )
        self.assertEqual(_jsonld_records(soup, "https://www.booking.com"), [])

    def test_booking_direct_hotel_link_fallback_extracts_properties(self):
        soup = BeautifulSoup(
            '<a href="/hotel/in/imperial.html">The Imperial, New Delhi</a><a href="/hotel/in/leela.html">The Leela Palace New Delhi</a>',
            "html.parser",
        )
        records, _ = extract_template_records(soup, "https://www.booking.com/city/in/new-delhi.html")
        self.assertEqual([record["business_name"] for record in records], ["The Imperial, New Delhi", "The Leela Palace New Delhi"])


if __name__ == "__main__":
    unittest.main()
