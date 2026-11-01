"""Prompt-to-plan and constrained selector execution for the local API."""
import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .discovery import _heuristic_records, _jsonld_records, _rendered_html
from .extraction import USER_AGENT, _robots_allowed, build_session, safe_public_url
from .templates import extract_template_records, template_for_url


DEFAULT_FIELDS = {"name": "", "address": "", "phone": "", "email": "", "website": ""}
GENERIC_SELECTORS = {
    "card": "article, [class*='card'], [class*='listing'], [class*='result'], [class*='business'], [class*='venue']",
    "name": "h1, h2, h3, h4, [class*='title'], [class*='name']",
    "address": "[class*='address'], [itemprop='address']",
    "phone": "a[href^='tel:']",
    "email": "a[href^='mailto:']",
    "website": "a[href]",
    "city": "[class*='city'], [class*='location'], [itemprop='addressLocality']",
    "postal_code": "[class*='postal'], [class*='zip'], [itemprop='postalCode']",
    "category": "[class*='category'], [class*='type'], [itemprop='category']",
}


@dataclass
class ExecutionPlan:
    source_url: str
    prompt: str
    selectors: Dict[str, str]
    fields: List[str]
    browser_mode: bool = False
    max_records: int = 100
    max_pages: int = 5
    request_timeout: int = 15
    lead_generation: Dict = None
    warnings: List[str] = None
    execution_steps: List[str] = None

    def to_dict(self):
        value = asdict(self)
        value["lead_generation"] = value["lead_generation"] or {}
        value["warnings"] = value["warnings"] or []
        value["execution_steps"] = value["execution_steps"] or []
        return value


def _requested_fields(prompt):
    return ["name", "address", "city", "postal_code", "phone", "email", "website", "category"]


def _template_selectors(url):
    domain, template = template_for_url(url)
    if not template:
        return {}, ""
    selectors = {"card": ", ".join(template["card"])}
    for field in ("name", "address", "phone"):
        selectors[field] = ", ".join(template[field])
    selectors["website"] = ", ".join(template["link"])
    selectors.update({"city": "[itemprop='addressLocality'], [class*='city'], [class*='location']", "postal_code": "[itemprop='postalCode'], [class*='postal'], [class*='zip']", "category": "[class*='category'], [class*='type']"})
    return selectors, domain


def _ai_selector_proposal(url, prompt, selectors, browser_mode):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return selectors, ""
    if not _robots_allowed(url):
        return selectors, "AI selector proposal skipped because robots.txt disallows the page."
    try:
        if browser_mode:
            html, _ = _rendered_html(url)
        else:
            response = build_session().get(url, timeout=15, allow_redirects=True)
            response.raise_for_status()
            html = response.text
        soup = BeautifulSoup(html, "html.parser")
        for node in soup(["script", "style", "noscript"]):
            node.decompose()
        snapshot = str(soup)[:18000]
        schema = {
            "type": "object", "additionalProperties": False,
            "properties": {field: {"type": "string"} for field in ("card", "name", "address", "phone", "email", "website")},
            "required": ["card", "name", "address", "phone", "email", "website"],
        }
        payload = {
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "input": [{"role": "system", "content": "Return CSS selectors only. Selectors must target visible public listing fields. Do not invent data or provide code."}, {"role": "user", "content": json.dumps({"url": url, "request": prompt, "existing_selectors": selectors, "html": snapshot})}],
            "text": {"format": {"type": "json_schema", "name": "scraper_selectors", "strict": True, "schema": schema}},
        }
        response = requests.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=30)
        response.raise_for_status()
        proposal = json.loads(response.json().get("output_text", "{}"))
        if all(isinstance(proposal.get(field), str) and proposal[field].strip() for field in schema["required"]):
            return proposal, "AI proposed selectors from a bounded public HTML snapshot; review the plan before execution."
    except (requests.RequestException, ValueError, json.JSONDecodeError):
        pass
    return selectors, "AI selector proposal was unavailable; using local selectors."


def create_plan(url, prompt, browser_mode=False, max_records=100):
    if not safe_public_url(url):
        raise ValueError("Only safe public http(s) URLs are allowed.")
    selectors, domain = _template_selectors(url)
    warnings = []
    if not selectors:
        selectors = dict(GENERIC_SELECTORS)
        warnings.append("Generic selectors are a best-effort starting point; review the preview before exporting.")
    if browser_mode:
        warnings.append("Browser mode only renders public pages and ordinary consent banners; it does not bypass access controls.")
    if domain:
        warnings.append(f"Started from the maintained {domain} domain template.")
    ai_selectors, ai_warning = _ai_selector_proposal(url, prompt, selectors, browser_mode)
    selectors = ai_selectors
    if ai_warning:
        warnings.append(ai_warning)
    return ExecutionPlan(
        source_url=url,
        prompt=prompt or "Extract all available public business listing fields.",
        selectors=selectors,
        fields=_requested_fields(prompt),
        browser_mode=browser_mode,
        max_records=max(1, min(int(max_records), 500)),
        lead_generation={
            "verify_with_places": "verify name and address against Google Places when configured",
            "similarity_threshold": 80,
            "contacts_output": ["verified_business_name", "public_phone", "public_email", "evidence_urls"],
        },
        warnings=warnings,
        execution_steps=[
            "Validate URL, robots.txt, public DNS, redirects, and same-domain scope.",
            "Load the public page and inspect JSON-LD, semantic cards, and domain templates.",
            "In browser mode, scroll incrementally and activate ordinary load-more controls.",
            "Follow safe same-domain next-page links up to 5 pages.",
            "Deduplicate records and preserve source URLs as evidence.",
            "After extraction, query Google Places with business name and city, then compare address similarity.",
        ],
    )


def _first(card, selector):
    if not selector:
        return None
    for candidate in selector.split(","):
        node = card.select_one(candidate.strip())
        if node:
            return node
    return None


def _merge_records(record_groups, limit):
    merged, positions = [], {}
    for group in record_groups:
        for record in group:
            key = re.sub(r"\W+", "", str(record.get("business_name", "")).lower())
            if not key:
                continue
            if key in positions:
                existing = merged[positions[key]]
                for field, value in record.items():
                    if not existing.get(field) and value:
                        existing[field] = value
                continue
            positions[key] = len(merged)
            merged.append(dict(record))
            if len(merged) >= limit:
                return merged
    return merged


def execute_plan(plan_data):
    plan = ExecutionPlan(**{key: value for key, value in plan_data.items() if key in ExecutionPlan.__dataclass_fields__})
    if not safe_public_url(plan.source_url) or not _robots_allowed(plan.source_url):
        raise ValueError("The source URL is unsafe or disallowed by robots.txt.")
    if plan.browser_mode:
        html, final_url = _rendered_html_collection(plan)
    else:
        response = build_session().get(plan.source_url, timeout=plan.request_timeout, allow_redirects=True)
        response.raise_for_status()
        html, final_url = response.text, response.url
    if not safe_public_url(final_url):
        raise ValueError("The page redirected to an unsafe or private URL.")
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(plan.selectors.get("card", ""))[: plan.max_records]
    records, seen = [], set()
    for card in cards:
        name_node = _first(card, plan.selectors.get("name", ""))
        if not name_node:
            continue
        name = name_node.get_text(" ", strip=True)
        key = re.sub(r"\W+", "", name.lower())
        if len(name) < 3 or key in seen:
            continue
        seen.add(key)
        record = {"business_name": name, "source_url": final_url, "extraction_plan": plan.prompt}
        for field, output in (("address", "business_address"), ("city", "city"), ("postal_code", "postal_code"), ("phone", "public_phone"), ("email", "public_email"), ("category", "category")):
            if field in plan.fields:
                node = _first(card, plan.selectors.get(field, ""))
                record[output] = node.get("href", "") if field == "email" and node and node.get("href", "").startswith("mailto:") else (node.get_text(" ", strip=True) if node else "")
        if "website" in plan.fields:
            node = _first(card, plan.selectors.get("website", ""))
            record["website"] = urljoin(final_url, node.get("href", "")) if node else ""
        records.append(record)
    warnings = list(plan.warnings or [])
    if not records:
        structured_records = _jsonld_records(soup, final_url)
        template_records, _ = extract_template_records(soup, final_url, plan.max_records)
        heuristic_records = _heuristic_records(soup, final_url, plan.max_records)
        fallback = _merge_records((structured_records, template_records, heuristic_records), plan.max_records)
        for record in fallback:
            record["extraction_plan"] = plan.prompt
        records = fallback
        if records:
            warnings.append("The configured selectors found no cards; results came from a layered extraction fallback.")
        else:
            if "booking.com" in final_url and not soup.select("a[href*='/hotel/']"):
                warnings.append("Booking.com returned a generic or queryless page without public hotel links. Use a location-specific search URL with dates, or upload the page results URL from your browser.")
            else:
                warnings.append("No public records matched this plan. Try browser mode or review the selectors and page access restrictions.")
    return {"plan": plan.to_dict(), "records": records, "record_count": len(records), "warnings": warnings}


def _rendered_html_collection(plan):
    """Render public pages, scroll, use ordinary load-more, and follow next pages."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Browser mode needs Playwright. Install it, then run: playwright install chromium")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(plan.source_url, wait_until="domcontentloaded", timeout=plan.request_timeout * 1000)
        page_html = []
        for _ in range(plan.max_pages):
            for _ in range(4):
                try:
                    page.evaluate("""
                        () => {
                            const root = document.scrollingElement || document.documentElement || document.body;
                            if (root) window.scrollTo(0, root.scrollHeight || 0);
                        }
                    """)
                    page.wait_for_timeout(500)
                except Exception as error:
                    if "execution context was destroyed" in str(error).lower():
                        page.wait_for_load_state("domcontentloaded", timeout=plan.request_timeout * 1000)
                        continue
                    raise
            for label in ("Load more", "Show more", "More results"):
                try:
                    button = page.get_by_role("button", name=re.compile(label, re.I)).first
                    if button.is_visible() and button.is_enabled():
                        button.click(timeout=1000, no_wait_after=True)
                        page.wait_for_timeout(1000)
                        break
                except Exception:
                    pass
            page_html.append(page.content())
            try:
                next_link = page.locator("a[rel='next'], a[aria-label*='Next'], a[href*='page=']").first
                if next_link.is_visible() and next_link.get_attribute("href"):
                    next_url = urljoin(page.url, next_link.get_attribute("href"))
                    if safe_public_url(next_url) and urlparse(next_url).hostname == urlparse(plan.source_url).hostname:
                        page.goto(next_url, wait_until="domcontentloaded", timeout=plan.request_timeout * 1000)
                        page.wait_for_load_state("domcontentloaded", timeout=plan.request_timeout * 1000)
                        continue
            except Exception:
                pass
            break
        html, final_url = "\n".join(page_html) or page.content(), page.url
        browser.close()
    return html, final_url