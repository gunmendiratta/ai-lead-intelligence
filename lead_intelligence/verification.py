"""Independent Google Places verification for imported leads."""
from typing import Dict, Iterable, Optional

from .matching import compare_businesses
from .openstreetmap import OpenStreetMap
from .places import GooglePlaces


def verify_rows_with_places(
    rows: Iterable[Dict],
    name_column: str,
    address_column: str,
    city_column: str = "",
    postal_column: str = "",
    page_size: int = 5,
    progress: Optional[callable] = None,
):
    places = GooglePlaces()
    provider = places if places.available else OpenStreetMap()
    provider_name = "google_places" if places.available else "openstreetmap_nominatim"
    source_rows = list(rows)
    output = []
    for index, row in enumerate(source_rows, 1):
        original = {
            "name": row.get(name_column, ""),
            "address": row.get(address_column, ""),
            "city": row.get(city_column, "") if city_column else "",
            "postal_code": row.get(postal_column, "") if postal_column else "",
        }
        query = ", ".join(str(value).strip() for value in (original["name"], original["city"], original["address"]) if str(value).strip())
        best = None
        error = ""
        try:
            candidates = provider.text_search(query, page_size) if places.available else provider.search(original["name"], original["city"], original["address"], page_size)
            for candidate_record in candidates:
                candidate = {
                    "name": candidate_record.get("business_name", ""),
                    "address": candidate_record.get("business_address", ""),
                    "city": "",
                    "postal_code": "",
                }
                match = compare_businesses(original, candidate)
                if best is None or match.overall_score > best["match"].overall_score:
                    best = {"record": candidate_record, "match": match}
        except Exception as exc:
            error = str(exc)[:240]
        result = dict(row)
        if best:
            candidate_record, match = best["record"], best["match"]
            result.update({
                "places_business_name": candidate_record.get("business_name", ""),
                "places_business_address": candidate_record.get("business_address", ""),
                "places_phone": candidate_record.get("public_phone", ""),
                "places_website": candidate_record.get("website", ""),
                "places_source_url": candidate_record.get("source_url", ""),
                "places_category": candidate_record.get("category", ""),
                "verification_provider": provider_name,
                "places_name_similarity": match.name_similarity,
                "places_address_similarity": match.address_similarity,
                "places_overall_similarity": match.overall_score,
                "places_verification_status": "Verified" if match.overall_score >= 80 and match.status != "Rejected" else ("Rejected" if match.status == "Rejected" else "Needs Manual Review"),
                "places_verification_reason": match.reason,
            })
        else:
            result.update({
                "places_business_name": "", "places_business_address": "", "places_phone": "",
                "places_website": "", "places_source_url": "", "places_category": "",
                "places_name_similarity": None, "places_address_similarity": None,
                "places_overall_similarity": 0, "places_verification_status": "No Information Found",
                "places_verification_reason": error or "No Places candidate found.",
                "verification_provider": provider_name,
            })
        output.append(result)
        if progress:
            progress(index, len(source_rows))
    return output