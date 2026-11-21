"""Checks that need no AI: "don't want" words and sizes written in the listing text.

Used before any AI check (so clear rejects cost no tokens), and on their own in
"No AI" mode, where anything that passes is marked "unknown" for you to judge.
"""

import re

from hunter.listing import Listing
from hunter.spec import Hunt

CM_PER = {"mm": 0.1, "cm": 1, "m": 100, "in": 2.54, "ft": 30.48}
UNIT_WORDS = {
    "mm": "mm", "millimetre": "mm", "millimetres": "mm", "millimeter": "mm", "millimeters": "mm",
    "cm": "cm", "cms": "cm", "centimetre": "cm", "centimetres": "cm", "centimeter": "cm", "centimeters": "cm",
    "m": "m", "metre": "m", "metres": "m", "meter": "m", "meters": "m", "mtr": "m", "mtrs": "m",
    "in": "in", "inch": "in", "inches": "in", '"': "in", "”": "in",
    "ft": "ft", "foot": "ft", "feet": "ft", "'": "ft", "’": "ft",
}
_UNIT = "|".join(sorted((re.escape(word) for word in UNIT_WORDS), key=len, reverse=True))
_NUMBER = r"\d+(?:\.\d+)?"
# "200 x 90 x 85 cm" or "200cm x 90cm": the unit may come after each number or only the last.
_LABEL = r"(?:(?:w|d|h|l|width|depth|height|length)\s*:?\s*)?"
_SEPARATOR = rf"\s*(?:x|×|\*|by)\s*{_LABEL}"
_SIZE = rf"({_NUMBER})\s*(?:({_UNIT})(?![a-z]))?"
_DIMENSIONS = re.compile(rf"{_SIZE}(?:{_SEPARATOR}{_SIZE})+", re.I)
_SINGLE = re.compile(rf"({_NUMBER})\s*({_UNIT})(?![a-z])", re.I)
_FEET_INCHES = re.compile(r"(\d+)\s*(?:ft|feet|foot|'|’)\s*(\d+)\s*(?:in|inch|inches|\"|”)?", re.I)
NEGATIONS = ("no", "not", "non", "without", "never")
SMALLEST_CM, LARGEST_CM = 10, 1000


def measurements_cm(text: str) -> list[float]:
    """Every size written in the text, in cm (sizes too small or big to be furniture are dropped)."""
    found = []
    for match in _FEET_INCHES.finditer(text):
        found.append(int(match.group(1)) * CM_PER["ft"] + int(match.group(2)) * CM_PER["in"])
    text = _FEET_INCHES.sub(" ", text)
    for match in _DIMENSIONS.finditer(text):
        numbers = re.findall(_SIZE, match.group(0), re.I)
        last_unit = next((unit for _, unit in reversed(numbers) if unit), None)
        if not last_unit:
            continue
        found += [_to_cm(number, unit or last_unit) for number, unit in numbers]
    text = _DIMENSIONS.sub(" ", text)
    found += [_to_cm(number, unit) for number, unit in _SINGLE.findall(text)]
    return [round(size, 1) for size in found if SMALLEST_CM <= size <= LARGEST_CM]


def avoid_hits(hunt: Hunt, text: str) -> list[str]:
    """Don't-want phrases that appear in the text, unless written as "no leather" etc."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    hits = []
    for phrase in hunt.avoid:
        wanted = re.findall(r"[a-z0-9]+", phrase.lower())
        if wanted and _contains(words, wanted):
            hits.append(phrase)
    return hits


def text_reject(hunt: Hunt, listing: Listing) -> str | None:
    """A reason to reject from the text alone, or None."""
    text = f"{listing.title}\n{listing.description}"
    hits = avoid_hits(hunt, text)
    if hits:
        return f"Listing mentions {', '.join(hits)} (don't want)."
    if hunt.size:
        largest_allowed = max(hunt.size.values())
        too_big = [size for size in measurements_cm(text) if size > largest_allowed]
        if too_big:
            return (f"Listing gives a size of {max(too_big):g} cm, over the largest limit "
                    f"({largest_allowed:g} cm).")
    return None


def no_ai_verdict(hunt: Hunt, listing: Listing) -> tuple[str, str]:
    """For "No AI" mode: (reason, seller question) for a listing that passed the text checks."""
    sizes = measurements_cm(f"{listing.title}\n{listing.description}")
    size_note = f"Sizes in text: {', '.join(f'{size:g}' for size in sizes)} cm." if sizes else "No sizes in text."
    unchecked = f" Not checked: {'; '.join(hunt.musts)}" if hunt.musts else ""
    reason = f"No AI: passed the text checks. {size_note}{unchecked}"
    question = ""
    if not sizes and hunt.size:
        question = "Hi, is this still available? Could you tell me its measurements in cm? Thanks!"
    return reason, question


def _contains(words: list[str], wanted: list[str]) -> bool:
    for start in range(len(words) - len(wanted) + 1):
        if all(_same_word(want, word) for want, word in zip(wanted, words[start:start + len(wanted)])):
            if not any(word in NEGATIONS for word in words[max(0, start - 2):start]):
                return True
    return False


def _same_word(want: str, word: str) -> bool:
    return word == want or (len(want) > 3 and word.startswith(want))


def _to_cm(number: str, unit: str) -> float:
    return float(number) * CM_PER[UNIT_WORDS[unit.lower()]]
