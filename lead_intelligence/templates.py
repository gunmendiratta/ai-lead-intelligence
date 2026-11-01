"""Conservative selectors for well-known public travel listing pages.

These are extraction hints, not browser automation recipes. They are intentionally
small and may need updates when a website changes its public markup.
"""
import re
from urllib.parse import urljoin, urlparse


TEMPLATES = {
    "booking.com": {
        "card": ["[data-testid='property-card']", "[data-testid='property-card-container']", "div[class*='sr_property_block']", "div[class*='hotel-card']", "li[class*='hotel']"],
        "name": ["[data-testid='title']", "[data-testid='title-link']", "a[href*='/hotel/']", "h3", "h2"],
        "address": ["[data-testid='address']", "[class*='address']"],
        "phone": ["a[href^='tel:']"],
        "email": ["a[href^='mailto:']"],
        "link": ["a[data-testid='title-link']", "a[href*='/hotel/']", "a[href*='/hotel/']"],
    },
    "makemytrip.com": {
        "card": ["[class*='hotelCard']", "[class*='HotelCard']", "[class*='listingCard']"],
        "name": ["h3", "h2", "[class*='hotelName']", "[class*='HotelName']"],
        "address": ["[class*='address']", "[class*='location']"],
        "phone": ["a[href^='tel:']"],
        "email": ["a[href^='mailto:']"],
        "link": ["a[href*='/hotel/']", "a[href*='hotel']"],
    },
    "goibibo.com": {
        "card": ["[class*='HotelCard']", "[class*='hotelCard']", "[class*='listingCard']"],
        "name": ["h3", "h2", "[class*='hotelName']", "[class*='HotelName']"],
        "address": ["[class*='address']", "[class*='location']"],
        "phone": ["a[href^='tel:']"],
        "email": ["a[href^='mailto:']"],
        "link": ["a[href*='/hotel/']", "a[href*='hotel']"],
    },
}


def template_for_url(url):
    hostname = (urlparse(url).hostname or "").lower().removeprefix("www.")
    for domain, template in TEMPLATES.items():
        if hostname == domain or hostname.endswith("." + domain):
            return domain, template
    return "", None


def _first(card, selectors):
    for selector in selectors:
        found = card.select_one(selector)
        if found:
            return found
    return None


def extract_template_records(soup, source_url, limit=100):
    domain, template = template_for_url(source_url)
    if not template:
        return [], ""
    records, seen = [], set()
    cards = []
    for selector in template["card"]:
        cards.extend(soup.select(selector))
    for card in cards[:300]:
        name_node = _first(card, template["name"])
        if not name_node:
            continue
        name = name_node.get_text(" ", strip=True)
        key = " ".join(name.lower().split())
        if len(name) < 3 or key in seen:
            continue
        seen.add(key)
        address_node = _first(card, template["address"])
        phone_node = _first(card, template["phone"])
        link_node = _first(card, template["link"])
        records.append({
            "business_name": name,
            "business_address": address_node.get_text(" ", strip=True) if address_node else "",
            "city": "",
            "postal_code": "",
            "website": urljoin(source_url, link_node.get("href", "")) if link_node else "",
            "public_phone": phone_node.get_text(" ", strip=True) if phone_node else "",
            "source_url": source_url,
            "source_domain_template": domain,
            "discovery_method": "domain_template",
        })
        if len(records) >= limit:
            break
    if not records and domain == "booking.com":
        city_match = re.search(r"/city/[^/]+/([^./]+)", source_url)
        city = city_match.group(1).replace("-", " ").title() if city_match else ""
        for link_node in soup.select("a[href*='/hotel/']")[:500]:
            name = link_node.get_text(" ", strip=True)
            key = " ".join(name.lower().split())
            href = link_node.get("href", "")
            if len(name) < 4 or key in seen or name.lower() in {"hotel", "hotels", "होटल"} or "/hotel/index" in href:
                continue
            seen.add(key)
            records.append({
                "business_name": name,
                "business_address": "",
                "city": city,
                "postal_code": "",
                "website": urljoin(source_url, link_node.get("href", "")),
                "public_phone": "",
                "source_url": source_url,
                "source_domain_template": domain,
                "discovery_method": "domain_template_link_fallback",
            })
            if len(records) >= limit:
                break
    return records, domain