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
    assert in_tab({"status": "viewed", "verdict": "fits"}, "viewed")
    assert in_tab({"status": "interested", "verdict": "no"}, "interested")
    assert in_tab({"status": "rejected", "verdict": "fits"}, "rejected")
    assert in_tab({"status": None, "verdict": "no"}, "rejected")
    assert in_tab({"status": None, "verdict": "unknown"}, "new")


def test_status_survives_recheck(tmp_path):
    from hunter.store import Store
    store = Store(tmp_path / "x.db")
    store.save("sofa", listing(), 1.0, "unknown", "No sizes")
    store.set_status("sofa", "gumtree:1", "interested", "Contacted seller")
    store.save("sofa", listing(), 1.0, "fits", "Seller replied")
    [row] = store.listings("sofa")
    assert (row["status"], row["stage"], row["verdict"]) == ("interested", "Contacted seller", "fits")
    assert store.unviewed("sofa") == []


def test_town_name_picks_nearest_match(tmp_path):
    from hunter.geo import Geo
    from hunter.spec import Home
    geo = Geo(tmp_path / "cache.json")
    geo.cache = {"outcodes/CR0": [51.37, -0.08], "places/croydon": [[52.1, -0.1], [51.37, -0.1]]}
    assert geo.miles(Home(postcode="CR0 1AA"), None, "Croydon, London") < 2


def test_browser_links_use_only_outward_code():
    from hunter.links import browser_search_urls
    from hunter.spec import Home
    hunt = Hunt(slug="sofa", name="x", searches=["corner sofa"], max_price=100, max_distance=10,
                sites=["facebook", "preloved"])
    urls = dict(browser_search_urls(Home(postcode="CR0 3QS", gumtree_area="croydon"), hunt))
    assert "marketplace/croydon/search?query=corner+sofa&maxPrice=100&radius=16" in urls["facebook"]
    assert "location=CR0&" in urls["preloved"] and "3QS" not in urls["preloved"]


def test_store_keeps_trade_flag_and_first_seen(tmp_path):
    from hunter.store import Store
    store = Store(tmp_path / "x.db")
    store.save("sofa", listing(is_trade=True), 1.0, "no", "Trade")
    first = store.listings("sofa")[0]["found_at"]
    store.save("sofa", listing(is_trade=True), 1.0, "no", "Trade again")
    [again] = store.unviewed("sofa")
    assert again.is_trade and store.listings("sofa")[0]["found_at"] == first


def test_usage_line():
    from hunter.web import usage_line
    run = {"tokens": 120500, "checks": 4, "limits_before": {"five_hour": 58, "seven_day": 8},
           "limits_after": {"five_hour": 61, "seven_day": 8}}
    assert usage_line(run) == "120,500 tokens (4 Claude checks), 5-hour +3% (now 61%), week +0% (now 8%)"
    assert usage_line({**run, "limits_after": None}).endswith("plan % unknown")
    assert usage_line({**run, "mode": "basic"}).startswith("Basic AI: 120,500 tokens")


def test_modes_load_nothing_extra():
    command = check.claude_command("hi", check.MODES["basic"])
    assert "--strict-mcp-config" in command and command[command.index("--model") + 1] == "haiku"
    assert check.MODES["thorough"].photos > check.MODES["basic"].photos


def test_tally_adds_all_token_kinds():
    from hunter.usage import Tally
    tally = Tally()
    tally.add({"usage": {"input_tokens": 2, "cache_read_input_tokens": 10, "output_tokens": 5}, "total_cost_usd": 0.1})
    assert (tally.checks, tally.tokens, tally.cost_usd) == (1, 17, 0.1)


def test_last_checked_per_site(tmp_path):
    from hunter.store import Store
    from hunter.web import checked_today
    store = Store(tmp_path / "x.db")
    store.save_run({"hunts": ["sofa"], "sites_by_hunt": {"sofa": ["gumtree"]}})
    store.save_run({"hunts": ["sofa"], "site": "preloved"})
    store.save_run({"hunts": ["desk"], "site": "facebook"})
    assert set(store.last_checked("sofa")) == {"gumtree", "preloved"}
    assert checked_today("2026-11-21T07:30:00", today="2026-11-21")
    assert not checked_today("2026-11-20T23:00:00", today="2026-11-21")
    assert not checked_today(None)
