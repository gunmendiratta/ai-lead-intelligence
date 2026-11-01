import re
import unicodedata


_ABBREVIATIONS = {
    "street": "st", "strasse": "str", "straße": "str", "road": "rd",
    "avenue": "ave", "boulevard": "blvd", "place": "pl", "lane": "ln",
    "square": "sq", "switzerland": "ch", "swiss": "ch",
}


def clean_text(value):
    """Return a comparable, accent-insensitive representation of a value."""
    value = "" if value is None else str(value)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    words = [_ABBREVIATIONS.get(word, word) for word in value.split()]
    return " ".join(words)


def normalize_address(value):
    return clean_text(value)


def postal_code(value):
    match = re.search(r"\b\d{4,10}(?:-\d{3,5})?\b", "" if value is None else str(value))
    return match.group(0).replace(" ", "") if match else ""
