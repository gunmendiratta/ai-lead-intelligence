import ipaddress
import os
import re
import socket
import time
from html import unescape
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+(?![\w.+-])")
PHONE = re.compile(r"(?<!\w)(?:\+|00)?\d[\d\s()./-]{6,}\d(?!\w)")
USER_AGENT = "LeadIntelligenceBot/1.0 (public-business-contact-research)"


def build_session():
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.4,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def safe_public_url(url):
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return False
    if parsed.hostname.lower() in {"localhost", "localhost.localdomain"} or parsed.hostname.lower().endswith(".localhost"):
        return False
    try:
        parsed.port
        addresses = socket.getaddrinfo(parsed.hostname, None)
        return all(ipaddress.ip_address(address[4][0]).is_global for address in addresses)
    except (socket.gaierror, ValueError, UnicodeError):
        return False


def _robots_allowed(url):
    parsed = urlparse(url)
    robots = RobotFileParser(url=f"{parsed.scheme}://{parsed.netloc}/robots.txt")
    try:
        robots.read()
        return robots.can_fetch(USER_AGENT, url)
    except Exception:
        return False  # conservative when robots.txt cannot be read


def extract_website_contacts(url, timeout=10, max_pages=3):
    """Crawl only a public site and same-domain contact/about pages, respecting robots.txt."""
    if not safe_public_url(url):
        return {"error": "Unsafe or invalid URL", "source_urls": []}
    session = build_session()
    queue, visited, texts, emails, phones, social = [url], set(), [], set(), set(), set()
    source_domain = urlparse(url).hostname.lower().removeprefix("www.")
    while queue and len(visited) < max_pages:
        current = queue.pop(0)
        if current in visited or not _robots_allowed(current):
            continue
        try:
            response = session.get(current, timeout=timeout, allow_redirects=True)
            if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
                continue
            if not safe_public_url(response.url):
                continue
            response_domain = urlparse(response.url).hostname.lower().removeprefix("www.")
            if response_domain != source_domain:
                continue
            visited.add(response.url)
            soup = BeautifulSoup(response.text, "html.parser")
            for unwanted in soup(["script", "style", "noscript"]):
                unwanted.decompose()
            page_text = unescape(soup.get_text(" ", strip=True))
            texts.append(page_text[:6000])
            emails.update(match.lower() for match in EMAIL.findall(page_text))
            phones.update(" ".join(match.split()) for match in PHONE.findall(page_text))
            base_domain = urlparse(response.url).hostname.lower().removeprefix("www.")
            for link in soup.select("a[href]"):
                href = urljoin(response.url, link["href"])
                domain = urlparse(href).hostname or ""
                normalized_domain = domain.lower().removeprefix("www.")
                if normalized_domain in {"facebook.com", "instagram.com", "linkedin.com"}:
                    social.add(href)
                if normalized_domain == base_domain and safe_public_url(href) and any(word in (link.get_text() + href).lower() for word in ("contact", "about", "impressum", "legal")):
                    if href not in visited and href not in queue:
                        queue.append(href)
            time.sleep(float(os.getenv("LEAD_REQUEST_DELAY", "0.2")))
        except requests.RequestException:
            continue
    return {"emails": sorted(emails), "phones": sorted(phones), "social_links": sorted(social), "source_urls": sorted(visited), "website_text": " ".join(texts)[:12000], "error": "" if visited else "No crawlable public pages found"}
