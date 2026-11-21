import json

from hunter import check, gumtree
from hunter.geo import haversine_miles, outward_code
from hunter.listing import Listing
from hunter.spec import Hunt
from hunter.web import in_tab

SOFA = Hunt(slug="sofa", name="Corner sofa", searches=["corner sofa", "l shaped sofa"],
            max_price=100, max_distance=10, sites=["gumtree"])


def listing(**changes):
    base = dict(site="gumtree", site_id="1", url="u", title="Corner sofa", price=50)
    return Listing(**{**base, **changes})


def test_search_words_match_loosely():
    assert check.matches_searches(SOFA, "Grey L-shape chaise sofa, must go")
    assert check.matches_searches(SOFA, "CORNER SOFAS for sale")
    assert not check.matches_searches(SOFA, "Oak dining table")


def test_quick_reject_rules():
    assert check.quick_reject(SOFA, listing(price=150), 2).verdict == check.NO
    assert "miles" in check.quick_reject(SOFA, listing(), 12.5).reason
    assert check.quick_reject(SOFA, listing(is_trade=True), 1).verdict == check.NO
    assert check.quick_reject(SOFA, listing(), None) is None


def test_claude_answer_is_parsed_and_checked():
    out = json.dumps({"result": 'Sure: {"verdict":"unknown","reason":"No sizes.","seller_question":"How wide?"}'})
    verdict = check.parse_claude_answer(out)
    assert (verdict.verdict, verdict.seller_question) == ("unknown", "How wide?")
    assert check.parse_claude_answer("garbage").verdict == check.UNKNOWN
    odd = json.dumps({"result": '{"verdict":"maybe"}'})
    assert check.parse_claude_answer(odd).verdict == check.UNKNOWN


def test_gumtree_category_page():
    data = {"mainEntity": {"itemListElement": [{"item": {
        "name": " Corner sofa ", "url": "https://www.gumtree.com/p/sofas-couches/corner-sofa/123",
        "image": "https://img.gumtree.com/a/b/86", "description": "Grey", "offers": {"price": 40}}}]}}
    page = f'<script type="application/ld+json">{json.dumps(data)}</script>'
    [found] = gumtree.parse_category_page(page)
    assert (found.site_id, found.title, found.price) == ("123", "Corner sofa", 40)


def test_gumtree_listing_page():
    page = ('"listingDetails":{"age":"2 days","isTrade":false,"location":"Shirley, London","price":60},'
            '"postalCode":"CR05AB"'
            '<p itemProp="description" class="x">Width 190cm<br/>Chaise on the right &amp; clean</p>'
            '"image":["https://img.gumtree.com/abc_D/def-1/86"]'
            '<img src="https://img.gumtree.com/other/similar-2/86">')
    found = listing()
    gumtree.parse_listing_page(page, found)
    assert found.postcode == "CR05AB" and found.price == 60 and found.place == "Shirley, London"
    assert found.description == "Width 190cm\nChaise on the right & clean"
    assert found.image_urls == ["https://img.gumtree.com/abc_D/def-1/86"]


def test_geo_helpers():
    assert outward_code("cr0 3qs") == "CR0"
    assert outward_code("SW1A1AA") == "SW1A"
    london_to_croydon = haversine_miles((51.5074, -0.1278), (51.3762, -0.0982))
    assert 8.5 < london_to_croydon < 9.5


def test_tabs():
    assert in_tab({"viewed_at": "x", "verdict": "fits"}, "viewed")
    assert in_tab({"viewed_at": None, "verdict": "no"}, "rejected")
    assert in_tab({"viewed_at": None, "verdict": "unknown"}, "new")


def test_town_name_picks_nearest_match(tmp_path):
    from hunter.geo import Geo
    from hunter.spec import Home
    geo = Geo(tmp_path / "cache.json")
    geo.cache = {"outcodes/CR0": [51.37, -0.08], "places/croydon": [[52.1, -0.1], [51.37, -0.1]]}
    assert geo.miles(Home(postcode="CR0 1AA"), None, "Croydon, London") < 2
