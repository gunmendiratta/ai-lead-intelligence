from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional

import requests

from .cache import Cache
from .extraction import extract_website_contacts
from .matching import compare_businesses


@dataclass
class Columns:
    name: str
    address: str
    city: str = ""
    postal_code: str = ""
    website: str = ""
    candidate_name: str = ""
    candidate_address: str = ""
    candidate_city: str = ""
    candidate_postal_code: str = ""
    candidate_source_url: str = ""


def _quality_score(website, details, original, match, category=""):
    score = 0
    score += 20 if website else 0
    score += 20 if details.get("emails") else 0
    score += 15 if details.get("phones") else 0
    score += 15 if len(original.get("address", "").strip()) >= 8 else 0
    score += {"Verified": 30, "Probable Match": 20, "Needs Manual Review": 10}.get(match.status, 0)
    if category and original.get("category"):
        score += 10 if category.lower() in str(original["category"]).lower() else 0
    return min(100, score)


def process_rows(rows: Iterable[Dict], columns: Columns, crawl_websites=False, discover_websites=False, ai_review=False, progress: Optional[Callable] = None):
    cache = Cache()
    reviewer = None
    if ai_review:
        from .ai_verifier import OpenAIReviewer
        reviewer = OpenAIReviewer()
    search_provider = None
    if discover_websites:
        from .search import GoogleProgrammableSearch
        search_provider = GoogleProgrammableSearch()
    rows = list(rows)
    results = []
    for index, row in enumerate(rows, 1):
        original = {"name": row.get(columns.name, ""), "address": row.get(columns.address, ""), "city": row.get(columns.city, "") if columns.city else "", "postal_code": row.get(columns.postal_code, "") if columns.postal_code else "", "category": row.get("category", "")}
        website = row.get(columns.website, "").strip() if columns.website else ""
        if not website and search_provider and search_provider.available:
            try:
                website = search_provider.find_website(original["name"], original["address"], original["city"])
            except requests.RequestException:
                website = ""
        details = {"emails": [], "phones": [], "source_urls": [], "website_text": "", "error": "Website enrichment disabled"}
        if crawl_websites and website:
            details = cache.get(website) or extract_website_contacts(website)
            if not details.get("error"):
                cache.set(website, details)
        candidate = {
            "name": row.get(columns.candidate_name, "") if columns.candidate_name else "",
            "address": row.get(columns.candidate_address, "") if columns.candidate_address else "",
            "city": row.get(columns.candidate_city, "") if columns.candidate_city else "",
            "postal_code": row.get(columns.candidate_postal_code, "") if columns.candidate_postal_code else "",
        }
        candidate_source_url = row.get(columns.candidate_source_url, "") if columns.candidate_source_url else ""
        has_candidate = any(str(value).strip() for value in candidate.values())
        independent_candidate = bool(candidate_source_url.strip())
        match = compare_businesses(original, candidate) if has_candidate and independent_candidate else compare_businesses({}, {})
        if has_candidate and not independent_candidate:
            match.status = "No Information Found"
            match.reason = "Independent candidate source URL is required before verification."
        ai_result = {"recommendation": "not_run", "confidence": None, "reason": "Deterministic decision retained."}
        if reviewer and reviewer.available and match.status in {"Probable Match", "Needs Manual Review"}:
            try:
                ai_result = reviewer.review(
                    original,
                    candidate,
                    match,
                    details.get("website_text", ""),
                    {"emails": details.get("emails", []), "phones": details.get("phones", []), "social_links": details.get("social_links", [])},
                )
            except (requests.RequestException, ValueError) as error:
                ai_result = {"recommendation": "error", "confidence": None, "reason": str(error)[:180]}
        result = dict(row)
        result.update({
            "official_website": website, "public_email": "; ".join(details.get("emails", [])), "public_phone": "; ".join(details.get("phones", [])),
            "social_links": "; ".join(details.get("social_links", [])), "contact_page_urls": "; ".join(details.get("source_urls", [])),
            "contact_source_urls": "; ".join(details.get("source_urls", [])), "matched_business_name": candidate["name"], "matched_business_address": candidate["address"],
            "candidate_source_url": candidate_source_url,
            "name_similarity_score": match.name_similarity, "address_similarity_score": match.address_similarity, "city_similarity_score": match.city_similarity,
            "postal_similarity_score": match.postal_similarity, "overall_match_score": match.overall_score, "final_verification_status": match.status,
            "verification_reason": match.reason, "processing_status": details.get("error") or "Processed",
            "ai_recommendation": ai_result.get("recommendation"), "ai_confidence_score": ai_result.get("confidence"), "ai_reason": ai_result.get("reason"),
            "ai_warnings": "; ".join(ai_result.get("warnings", [])),
            "lead_quality_score": _quality_score(website, details, original, match, row.get("category", "")),
        })
        results.append(result)
        if progress:
            progress(index, len(rows))
    return results
