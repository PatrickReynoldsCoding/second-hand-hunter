"""Decide whether a listing fits a hunt.

Quick rules first (words, price, distance, trade sellers). Listings that pass
go to Claude (headless Claude Code), which reads the text and photos against
the plain-English must-haves and the size limits.
"""

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from hunter import net
from hunter.listing import Listing
from hunter.spec import Hunt
from hunter.usage import Tally

FITS, NO, UNKNOWN = "fits", "no", "unknown"
CLAUDE_TIMEOUT_SECONDS = 300


@dataclass
class Verdict:
    verdict: str
    reason: str
    seller_question: str = ""


def matches_searches(hunt: Hunt, text: str) -> bool:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return any(_phrase_in(phrase, words) for phrase in hunt.searches)


def quick_reject(hunt: Hunt, listing: Listing, miles: float | None) -> Verdict | None:
    if listing.is_trade:
        return Verdict(NO, "Trade seller (usually new stock).")
    if listing.price is not None and listing.price > hunt.max_price:
        return Verdict(NO, f"£{listing.price:g} is over £{hunt.max_price:g}.")
    if miles is not None and miles > hunt.max_distance:
        return Verdict(NO, f"{miles} miles away, over {hunt.max_distance:g}.")
    return None


def claude_check(hunt: Hunt, listing: Listing, miles: float | None, tally: Tally | None = None) -> Verdict:
    with tempfile.TemporaryDirectory() as folder:
        photos = _download_photos(listing, Path(folder))
        prompt = _prompt(hunt, listing, miles, photos)
        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--output-format", "json", "--allowedTools", "Read"],
                capture_output=True, text=True, timeout=CLAUDE_TIMEOUT_SECONDS, cwd=folder,
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return Verdict(UNKNOWN, f"Not checked: {error}")
    if tally is not None:
        try:
            tally.add(json.loads(result.stdout))
        except ValueError:
            pass
    return parse_claude_answer(result.stdout)


def parse_claude_answer(stdout: str) -> Verdict:
    try:
        text = json.loads(stdout)["result"]
        answer = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    except (ValueError, KeyError, AttributeError, TypeError):
        return Verdict(UNKNOWN, "Not checked: Claude's answer couldn't be read.")
    verdict = answer.get("verdict")
    if verdict not in (FITS, NO, UNKNOWN):
        verdict = UNKNOWN
    return Verdict(verdict, answer.get("reason", ""), answer.get("seller_question", ""))


def _phrase_in(phrase: str, words: list[str]) -> bool:
    wanted = re.findall(r"[a-z0-9]+", phrase.lower())
    return all(any(_same_word(want, word) for word in words) for want in wanted)


def _same_word(want: str, word: str) -> bool:
    if len(want) <= 2 or len(word) <= 2:
        return want == word
    return word.startswith(want) or want.startswith(word)


def _download_photos(listing: Listing, folder: Path) -> list[Path]:
    photos = []
    for number, url in enumerate(listing.image_urls, start=1):
        try:
            data = net.fetch(url)
        except net.FetchError:
            continue
        path = folder / f"photo{number}.jpg"
        path.write_bytes(data)
        photos.append(path)
    return photos


def _prompt(hunt: Hunt, listing: Listing, miles: float | None, photos: list[Path]) -> str:
    limits = "\n".join(f"- {name}: {value} cm" for name, value in hunt.size.items()) or "- none"
    musts = "\n".join(f"- {rule}" for rule in hunt.musts) or "- none"
    avoid = "\n".join(f"- {thing}" for thing in hunt.avoid) or "- none"
    photo_list = "\n".join(f"- {path}" for path in photos) or "- no photos"
    return f"""You check second-hand listings against a buyer's spec. Look at the photos with the Read tool.

Item wanted: {hunt.name}
Size limits:
{limits}
Must-haves:
{musts}
Don't want (any of these means "no"):
{avoid}

Listing: {listing.title}
Price: {listing.price}  Distance: {miles if miles is not None else "unknown"} miles
Description:
{listing.description[:4000]}

Photos:
{photo_list}

Decide:
- "fits" only if every must-have and size limit is clearly met (from text, or clearly visible in photos).
- "no" if any must-have or limit is clearly broken, it has anything from "Don't want", or it isn't the item wanted.
- "unknown" if something can't be told. Then write a short, friendly question to the seller asking only for what's missing.
Photos are often mirrored or taken from odd angles: say in the reason what you based any orientation call on.

Reply with only JSON: {{"verdict": "fits|no|unknown", "reason": "one sentence", "seller_question": "" }}"""
