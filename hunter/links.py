"""Search links for sites that are checked in your own browser, not automatically.

Facebook needs you logged in and blocks bots; Preloved's robots.txt blocks
automated searching. So these are opened on request, in your browser.
"""

from urllib.parse import urlencode

from hunter.geo import outward_code
from hunter.spec import Home, Hunt

BROWSER_SITES = ("facebook", "preloved")
KM_PER_MILE = 1.609


def browser_search_urls(home: Home, hunt: Hunt) -> list[tuple[str, str]]:
    urls = []
    for words in hunt.searches:
        if "facebook" in hunt.sites:
            area = home.facebook_area or home.gumtree_area or "london"
            query = urlencode({"query": words, "maxPrice": int(hunt.max_price),
                               "radius": round(hunt.max_distance * KM_PER_MILE)})
            urls.append(("facebook", f"https://www.facebook.com/marketplace/{area}/search?{query}"))
        if "preloved" in hunt.sites:
            query = urlencode({"keyword": words, "location": outward_code(home.postcode),
                               "distance": int(hunt.max_distance), "price_max": int(hunt.max_price)})
            urls.append(("preloved", f"https://www.preloved.co.uk/search?{query}"))
    return urls
