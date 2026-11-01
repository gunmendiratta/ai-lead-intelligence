from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from typing import Optional

from .normalization import clean_text, normalize_address, postal_code

try:
    from rapidfuzz.fuzz import token_set_ratio
except ImportError:  # Keeps the project usable before optional dependencies are installed.
    def token_set_ratio(left, right):
        left_tokens, right_tokens = set(left.split()), set(right.split())
        if not left_tokens or not right_tokens:
            return 0
        overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        sequence = SequenceMatcher(None, left, right).ratio()
        return round(100 * max(overlap, sequence))


@dataclass
class MatchResult:
    name_similarity: Optional[float]
    address_similarity: Optional[float]
    city_similarity: Optional[float]
    postal_similarity: Optional[float]
    overall_score: float
    status: str
    reason: str

    def to_dict(self):
        return asdict(self)


def _score(left, right, normalizer=clean_text):
    left, right = normalizer(left), normalizer(right)
    if not left or not right:
        return None
    return round(float(token_set_ratio(left, right)), 1)


def compare_businesses(original, candidate, high_threshold=90, probable_threshold=75):
    """Explainable match score. Missing evidence is excluded, never treated as perfect."""
    name = _score(original.get("name"), candidate.get("name"))
    address = _score(original.get("address"), candidate.get("address"), normalize_address)
    city = _score(original.get("city"), candidate.get("city"))
    original_postal, candidate_postal = postal_code(original.get("postal_code") or original.get("address")), postal_code(candidate.get("postal_code") or candidate.get("address"))
    postal = 100.0 if original_postal and candidate_postal and original_postal == candidate_postal else (0.0 if original_postal and candidate_postal else None)
    weights = [(name, .35), (address, .45), (city, .10), (postal, .10)]
    available = [(score, weight) for score, weight in weights if score is not None]
    overall = round(sum(score * weight for score, weight in available) / sum(weight for _, weight in available), 1) if available else 0.0
    hard_location_conflict = postal == 0 or (city is not None and city < 35 and address is not None and address < 45)
    same_name_different_location = name is not None and name >= high_threshold and address is not None and address < 45
    if hard_location_conflict or same_name_different_location:
        status, reason = "Rejected", "Strong name evidence conflicts with the candidate location."
    elif overall >= high_threshold and name is not None and (address is not None or postal == 100):
        status, reason = "Verified", "Strong name and location evidence."
    elif overall >= probable_threshold and name is not None:
        status, reason = "Probable Match", "Some matching evidence; review location evidence before confirmation."
    elif not available:
        status, reason = "No Information Found", "No candidate business details were available to compare."
    else:
        status, reason = "Needs Manual Review", "Evidence is incomplete or below the verification threshold."
    return MatchResult(name, address, city, postal, overall, status, reason)
