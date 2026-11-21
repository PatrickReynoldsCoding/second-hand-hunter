"""The daily run: search every site for every active hunt, check new listings."""

import logging

from hunter import check, ebay, gumtree
from hunter.geo import Geo
from hunter.listing import Listing
from hunter.spec import Hunt, Profile
from hunter.store import DATA_DIR, Store

log = logging.getLogger("hunter")


def run_profile(profile: Profile, store: Store) -> dict[str, int]:
    geo = Geo(DATA_DIR / "geo-cache.json")
    counts = {}
    for hunt in profile.hunts:
        if hunt.active:
            counts[hunt.slug] = run_hunt(profile, hunt, store, geo)
    return counts


def run_hunt(profile: Profile, hunt: Hunt, store: Store, geo: Geo) -> int:
    new = 0
    for listing in _search_sites(profile, hunt):
        if store.known(hunt.slug, listing.key):
            continue
        if not check.matches_searches(hunt, f"{listing.title} {listing.description}"):
            continue
        if listing.price is not None and listing.price > hunt.max_price:
            store.save(hunt.slug, listing, None, check.NO, f"£{listing.price:g} is over £{hunt.max_price:g}.")
            continue
        add_listing(profile, hunt, listing, store, geo, fetch_details=True)
        new += 1
    return new


def add_listing(profile: Profile, hunt: Hunt, listing: Listing, store: Store, geo: Geo,
                fetch_details: bool) -> check.Verdict:
    if fetch_details and listing.site == "gumtree":
        try:
            gumtree.add_details(listing)
        except Exception as error:  # one bad page shouldn't stop the run
            log.warning("details failed for %s: %s", listing.url, error)
    miles = geo.miles(profile.home, listing.postcode, listing.place)
    verdict = check.quick_reject(hunt, listing, miles) or check.claude_check(hunt, listing, miles)
    store.save(hunt.slug, listing, miles, verdict.verdict, verdict.reason, verdict.seller_question)
    log.info("%s %s: %s", verdict.verdict, listing.title, verdict.reason)
    return verdict


def _search_sites(profile: Profile, hunt: Hunt) -> list[Listing]:
    found = []
    if "gumtree" in hunt.sites and hunt.gumtree_category and profile.home.gumtree_area:
        try:
            found += gumtree.search(hunt.gumtree_category, profile.home.gumtree_area)
        except Exception as error:
            log.warning("gumtree search failed: %s", error)
    if "ebay" in hunt.sites:
        found += ebay.search(hunt, profile.home)
    return found
