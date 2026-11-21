"""Gumtree: reads the first page of a category in an area, then each new listing.

Gumtree's robots.txt blocks /search, any address with "?", and page 2 onwards,
so this only reads the allowed category page and the listing pages (/p/...).
"""

import html
import json
import re

from hunter import net
from hunter.listing import Listing

BASE = "https://www.gumtree.com"
MAX_PHOTOS = 40  # all of them, in practice; AI checks use fewer


def category_url(category: str, area: str) -> str:
    return f"{BASE}/{category.strip('/')}/uk/{area}"


def search(category: str, area: str) -> list[Listing]:
    return parse_category_page(net.fetch_text(category_url(category, area)))


def parse_category_page(page: str) -> list[Listing]:
    listings = []
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        data = json.loads(block)
        items = data.get("mainEntity", {}).get("itemListElement", [])
        for entry in items:
            listings.append(_listing_from_summary(entry["item"]))
    return listings


def add_details(listing: Listing) -> None:
    parse_listing_page(net.fetch_text(listing.url), listing)


def parse_listing_page(page: str, listing: Listing) -> None:
    details = _json_object_after(page, '"listingDetails":')
    if details:
        listing.place = details.get("location")
        listing.age = details.get("age")
        listing.is_trade = bool(details.get("isTrade"))
        listing.price = details.get("price", listing.price)
    postcode = re.search(r'"postalCode":"([A-Z0-9 ]+)"', page)
    if postcode:
        listing.postcode = postcode.group(1)
    description = re.search(r'<p itemProp="description"[^>]*>(.*?)</p>', page, re.S)
    if description:
        listing.description = _plain_text(description.group(1))
    listing.image_urls = _own_photos(page)[:MAX_PHOTOS] or listing.image_urls


def _own_photos(page: str) -> list[str]:
    """The listing's photos only: the page also shows photos of similar listings."""
    gallery = re.search(r'"image":\[([^\]]*)\]', page)
    if not gallery:
        return []
    return re.findall(r'https://img\.gumtree\.com/[\w-]+/[\w-]+/\d+', gallery.group(1))


def _listing_from_summary(item: dict) -> Listing:
    url = item["url"]
    return Listing(
        site="gumtree",
        site_id=url.rstrip("/").rsplit("/", 1)[-1],
        url=url,
        title=item.get("name", "").strip(),
        price=item.get("offers", {}).get("price"),
        description=item.get("description", ""),
        image_urls=[item["image"]] if item.get("image") else [],
    )


def _json_object_after(page: str, marker: str) -> dict | None:
    start = page.find(marker)
    if start < 0:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(page, start + len(marker))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _plain_text(fragment: str) -> str:
    with_breaks = re.sub(r"<br\s*/?>", "\n", fragment)
    return html.unescape(re.sub(r"<[^>]+>", "", with_breaks)).strip()
