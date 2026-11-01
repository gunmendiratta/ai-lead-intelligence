"""Source-aware lead discovery without scraping search-engine result pages."""
import json
import re
from dataclasses import dataclass
from typing import Dict, List
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .extraction import USER_AGENT, _robots_allowed, build_session, safe_public_url
from .templates import extract_template_records, template_for_url


@dataclass
class DiscoveryResult:
    records: List[Dict]
    source_type: str
    message: str = ""


def classify_source(url):
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    if host in {"google.com", "google.co.in", "google.ch", "google.de", "google.fr"}:
        return "google_maps" if "/maps" in urlparse(url).path else "search_engine"
    if host in {"bing.com", "duckduckgo.com", "search.yahoo.com", "yandex.com"}:
        return "search_engine"
    return "website"


def google_maps_query(url):
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    for key in ("q", "query"):
        if params.get(key):
            return params[key][0]
    match = re.search(r"/maps/search/([^/?]+)", parsed.path)
    return unquote(match.group(1).replace("+", " ")) if match else ""


def _address(value):
    if isinstance(value, dict):
        return ", ".join(str(value.get(key, "")) for key in ("streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry") if value.get(key))
    return str(value or "")


def _as_record(item, source_url):
    if not isinstance(item, dict):
        return None
    item = item.get("item", item)
    item_types = item.get("@type", [])
    if isinstance(item_types, str):
        item_types = [item_types]
    allowed_types = {"LocalBusiness", "Hotel", "Restaurant", "Organization", "TouristAccommodation", "LodgingBusiness"}
    if item_types and not any(item_type in allowed_types for item_type in item_types):
        return None
    if "Organization" in item_types and str(item.get("name", "")).strip().lower() in {"booking.com", "booking"}:
        return None
    name = item.get("name") or item.get("headline")
    if not name:
        return None
    return {
        "business_name": str(name).strip(), "business_address": _address(item.get("address")),
        "city": item.get("address", {}).get("addressLocality", "") if isinstance(item.get("address"), dict) else "",
        "postal_code": item.get("address", {}).get("postalCode", "") if isinstance(item.get("address"), dict) else "",
        "website": item.get("url", ""), "public_phone": item.get("telephone", ""),
        "source_url": source_url, "discovery_method": "structured_data",
    }


def _jsonld_records(soup, source_url):
    records = []
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data])
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("itemListElement"), list):
                for entry in item["itemListElement"]:
                    record = _as_record(entry, source_url)
                    if record:
                        records.append(record)
            else:
                record = _as_record(item, source_url)
                if record:
                    records.append(record)
    return records


def _heuristic_records(soup, source_url, limit=80):
    records, seen = [], set()
    selector = "article, [class*='card'], [class*='listing'], [class*='result'], [class*='property'], [class*='business']"
    for card in soup.select(selector)[:300]:
        heading = card.select_one("h1, h2, h3, h4, [class*='title'], [class*='name']")
        if not heading:
            continue
        name = heading.get_text(" ", strip=True)
        normalized = re.sub(r"\W+", "", name.lower())
        if len(name) < 3 or normalized in seen:
            continue
        seen.add(normalized)
        link = card.select_one("a[href]")
        address = card.select_one("[class*='address'], [itemprop='address']")
        phone = card.select_one("[href^='tel:']")
        records.append({
            "business_name": name, "business_address": address.get_text(" ", strip=True) if address else "",
            "city": "", "postal_code": "", "website": urljoin(source_url, link.get("href", "")) if link else "",
            "public_phone": phone.get_text(" ", strip=True) if phone else "", "source_url": source_url,
            "discovery_method": "page_heuristic",
        })
        if len(records) >= limit:
            break
    return records


def _rendered_html(url):
    """Optional JavaScript renderer. It only dismisses ordinary consent banners."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Browser mode needs Playwright. Install dependencies, then run: playwright install chromium")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        for label in ("Accept", "Accept all", "I agree", "Allow all"):
            try:
                page.get_by_role("button", name=re.compile(label, re.I)).first.click(timeout=700)
                break
            except Exception:
                pass
        page.wait_for_timeout(1200)
        html, final_url = page.content(), page.url
        browser.close()
    return html, final_url


def discover_from_website(url, browser_mode=False):
    if not safe_public_url(url):
        return DiscoveryResult([], "website", "Enter a public http(s) URL. Local, private, and invalid addresses are blocked.")
    if not _robots_allowed(url):
        return DiscoveryResult([], "website", "The site's robots.txt does not allow this crawler to fetch the page.")
    try:
        if browser_mode:
            html, final_url = _rendered_html(url)
        else:
            response = build_session().get(url, timeout=15, allow_redirects=True)
            response.raise_for_status()
            html, final_url = response.text, response.url
        if not safe_public_url(final_url):
            return DiscoveryResult([], "website", "The page redirected to an unsafe or private URL.")
    except (requests.RequestException, RuntimeError) as error:
        return DiscoveryResult([], "website", str(error))
    soup = BeautifulSoup(html, "html.parser")
    records = _jsonld_records(soup, final_url)
    if not records:
        records, template_domain = extract_template_records(soup, final_url)
    else:
        template_domain = ""
    records = records or _heuristic_records(soup, final_url)
    if records:
        return DiscoveryResult(records, "website", "")
    if template_for_url(final_url)[0]:
        return DiscoveryResult([], "website", "The supported domain template found no public listing cards. Try browser mode, or the site may require restricted content.")
    return DiscoveryResult([], "website", "No business cards detected. Try browser mode or use a domain-specific template.")
