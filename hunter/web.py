"""The review page, served on this computer only (http://localhost:8765).

Left: a sidebar to pick, add and edit profiles and hunts, and to search again.
Right: the listings for the chosen hunt, with tabs and a "viewed" button.
"""

import hashlib
import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse

from hunter import net, run, spec
from hunter.geo import Geo
from hunter.spec import Home, Hunt, Profile, SpecError
from hunter.store import DATA_DIR, store_for

PORT = 8765
STATIC = Path(__file__).resolve().parent / "static"
TABS = {"new": "To review", "viewed": "Viewed", "rejected": "Rejected"}
PHOTO_CACHE = DATA_DIR / "photos"
PHOTO_HOSTS = ("img.gumtree.com", "i.ebayimg.com", "scontent", "fbcdn.net", "preloved")
BADGES = {"fits": "✅ Fits", "unknown": "❓ Ask seller", "no": "❌ No"}
SITES = ["gumtree", "ebay", "facebook", "preloved"]


def serve(default_profile: str | None = None, port: int = PORT) -> None:
    handler = type("Handler", (_Handler,), {"default_profile": default_profile})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"Review page: http://localhost:{port}")
    server.serve_forever()


def in_tab(listing: dict, tab: str) -> bool:
    if listing["viewed_at"]:
        return tab == "viewed"
    if listing["verdict"] == "no":
        return tab == "rejected"
    return tab == "new"


# --- Searching in the background ---

class SearchJob:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.message = ""

    def start(self, profile_name: str, hunt_slug: str | None) -> bool:
        with self.lock:
            if self.running:
                return False
            self.running, self.message = True, "Searching…"
        threading.Thread(target=self._run, args=(profile_name, hunt_slug), daemon=True).start()
        return True

    def status(self) -> dict:
        return {"running": self.running, "message": self.message}

    def _run(self, profile_name: str, hunt_slug: str | None) -> None:
        try:
            profile = spec.load_profile(profile_name)
            store, geo = store_for(profile_name), Geo(DATA_DIR / "geo-cache.json")
            hunts = [h for h in profile.hunts if h.active and (hunt_slug is None or h.slug == hunt_slug)]
            rechecked = found = 0
            for hunt in hunts:
                self.message = f"Re-checking {hunt.name}…"
                rechecked += run.recheck_hunt(profile, hunt, store, geo)
                self.message = f"Searching sites for {hunt.name}…"
                found += run.run_hunt(profile, hunt, store, geo)
            self.message = f"Done: {found} new, {rechecked} re-checked."
        except Exception as error:
            self.message = f"Search failed: {error}"
        finally:
            self.running = False


JOB = SearchJob()


# --- Page ---

def render(profile_name: str | None, hunt_slug: str, tab: str, editing: str = "") -> str:
    profiles = spec.list_profiles()
    if not profiles:
        return _page(_sidebar(None, None, profiles, ""), "<p class='empty'>Add a profile to start.</p>")
    profile = spec.load_profile(profile_name if profile_name in profiles else profiles[0])
    hunt = next((h for h in profile.hunts if h.slug == hunt_slug), profile.hunts[0] if profile.hunts else None)
    sidebar = _sidebar(profile, hunt, profiles, editing)
    if hunt is None:
        return _page(sidebar, "<p class='empty'>No hunts yet. Use “+ New hunt”.</p>")
    listings = store_for(profile.name).listings(hunt.slug)
    tab_links = "".join(
        f'<a class="pill {"on" if key == tab else ""}" href="{_link(profile.name, hunt.slug, key)}">'
        f'{label} ({sum(in_tab(item, key) for item in listings)})</a>'
        for key, label in TABS.items()
    )
    shown = sorted((item for item in listings if in_tab(item, tab)),
                   key=lambda item: (item["verdict"] != "fits", item["found_at"]))
    cards = "".join(_card(profile.name, hunt.slug, item) for item in shown)
    return _page(sidebar, f'<h1>{html.escape(hunt.name)}</h1><nav class="tabs">{tab_links}</nav>'
                          f'<div class="cards">{cards or "<p class=empty>Nothing here.</p>"}</div>')


def _link(profile: str, hunt: str = "", tab: str = "", edit: str = "") -> str:
    params = {key: value for key, value in
              {"profile": profile, "hunt": hunt, "tab": tab, "edit": edit}.items() if value}
    return "/?" + urlencode(params)


def _sidebar(profile: Profile | None, hunt: Hunt | None, profiles: list[str], editing: str) -> str:
    esc = html.escape
    options = "".join(f'<option {"selected" if profile and name == profile.name else ""}>{esc(name)}</option>'
                      for name in profiles)
    parts = [f"""<section>
  <label class="row">Profile <select id="profile-pick">{options}</select></label>
  <button type="button" data-toggle="new-profile">+ New profile</button>
  {_new_profile_form()}
</section>"""]
    if profile:
        hunt_links = "".join(
            f'<a class="hunt {"on" if hunt and h.slug == hunt.slug else ""}" href="{_link(profile.name, h.slug)}">'
            f'{esc(h.name)}{"" if h.active else " (paused)"}</a>' for h in profile.hunts)
        parts.append(f"""<section>
  <h2>Hunts</h2>{hunt_links}
  <a class="hunt" href="{_link(profile.name, hunt.slug if hunt else "", edit="new")}">+ New hunt</a>
</section>""")
        new_hunt = editing == "new"
        if hunt or new_hunt:
            parts.append(_hunt_form(profile.name, None if new_hunt else hunt))
        parts.append(_home_form(profile))
        parts.append("""<section><button type="button" id="search-all">Search all hunts now</button>
  <p id="status" class="muted"></p></section>""")
    return "".join(parts)


def _home_form(profile: Profile) -> str:
    home = profile.home
    fields = [("postcode", "Postcode", home.postcode), ("gumtree_area", "Gumtree area", home.gumtree_area),
              ("facebook_area", "Facebook area", home.facebook_area),
              ("lat", "Latitude (optional)", home.lat), ("lon", "Longitude (optional)", home.lon)]
    return f"""<details><summary>Home: {html.escape(home.postcode)}</summary>
<form class="api" data-api="/api/home" data-profile="{html.escape(profile.name)}">
  {"".join(_input(name, label, value) for name, label, value in fields)}
  <button>Save home</button>
</form></details>"""


def _hunt_form(profile: str, hunt: Hunt | None) -> str:
    esc = html.escape
    blank = Hunt(slug="", name="", searches=[], max_price=100, max_distance=10, sites=["gumtree"])
    h = hunt or blank
    size = "\n".join(f"{key} = {value:g}" for key, value in h.size.items())
    sites = "".join(f'<label class="check"><input type="checkbox" name="sites" value="{site}" '
                    f'{"checked" if site in h.sites else ""}> {site}</label>' for site in SITES)
    slug = (f'<input type="hidden" name="slug" value="{esc(h.slug)}">' if hunt else
            _input("slug", "Short id (e.g. desk)", ""))
    delete = (f'<button type="button" class="danger" data-delete="{esc(h.slug)}">Delete hunt</button>'
              if hunt else "")
    return f"""<details {"open" if not hunt else ""}><summary>{"Edit spec" if hunt else "New hunt"}</summary>
<form class="api" data-api="/api/hunt" data-profile="{esc(profile)}">
  {slug}
  {_input("name", "Name", h.name)}
  <label class="check"><input type="checkbox" name="active" {"checked" if h.active else ""}> Active</label>
  {_textarea("searches", "Search words (one per line)", "\n".join(h.searches))}
  {_input("max_price", "Max price (£)", f"{h.max_price:g}", "number")}
  {_input("max_distance", "Max distance (miles)", f"{h.max_distance:g}", "number")}
  <fieldset><legend>Sites</legend>{sites}</fieldset>
  {_textarea("size", "Size limits in cm (one per line, e.g. width_max = 200)", size)}
  {_textarea("musts", "Must-haves (one per line, plain English)", "\n".join(h.musts))}
  {_input("gumtree_category", "Gumtree category path", h.gumtree_category)}
  <div class="buttons"><button name="then" value="">Save</button>
  <button name="then" value="search" class="primary">Save and search again</button>{delete}</div>
</form></details>"""


def _new_profile_form() -> str:
    return f"""<form class="api hidden" id="new-profile" data-api="/api/profile">
  {_input("name", "Name (e.g. sam)", "")}{_input("postcode", "Postcode", "")}
  {_input("gumtree_area", "Gumtree area (e.g. croydon)", "")}
  <button>Create profile</button></form>"""


def _input(name: str, label: str, value, kind: str = "text") -> str:
    shown = "" if value is None else html.escape(str(value))
    step = ' step="any"' if kind == "number" else ""
    return f'<label>{label}<input name="{name}" type="{kind}"{step} value="{shown}"></label>'


def _textarea(name: str, label: str, value: str) -> str:
    rows = max(2, value.count("\n") + 2)
    return f'<label>{label}<textarea name="{name}" rows="{rows}">{html.escape(value)}</textarea></label>'


def _card(profile: str, hunt: str, item: dict) -> str:
    esc = html.escape
    photo = item["image_urls"][0] if item["image_urls"] else ""
    image = (f'<img src="/photo?u={quote(photo, safe="")}" alt="" loading="lazy">' if photo
             else '<div class="nophoto">No photo</div>')
    price = f"£{item['price']:g}" if item["price"] else "No price given"
    miles = f"{item['miles']} mi" if item["miles"] is not None else "distance unknown"
    question = ""
    if item["seller_question"]:
        question = (f'<p class="ask">{esc(item["seller_question"])}</p>'
                    f'<button class="copy" data-text="{esc(item["seller_question"])}">Copy question</button>')
    viewed = bool(item["viewed_at"])
    return f"""<article class="{esc(item['verdict'])}">
  <a href="{esc(item['url'])}" target="_blank" rel="noopener">{image}</a>
  <div class="body">
    <span class="badge">{BADGES.get(item['verdict'], item['verdict'])}</span> <span class="muted">{esc(item['site'])}</span>
    <h3><a href="{esc(item['url'])}" target="_blank" rel="noopener">{esc(item['title'])}</a></h3>
    <p class="muted"><b>{price}</b> · {miles} · {esc(item['place'] or '')}</p>
    <p class="reason">{esc(item['reason'] or '')}</p>
    {question}
    <button class="view primary" data-profile="{esc(profile)}" data-hunt="{esc(hunt)}" data-key="{esc(item['key'])}"
      data-viewed="{int(not viewed)}">{"Not viewed" if viewed else "Mark viewed"}</button>
  </div>
</article>"""


def _page(sidebar: str, main: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Second-hand hunter</title>
<link rel="stylesheet" href="/static/page.css"></head>
<body><aside>{sidebar}</aside><main>{main}</main><script src="/static/page.js"></script></body></html>"""


# --- Saving from the forms ---

def save_home(data: dict) -> None:
    home = Home(postcode=data.get("postcode", "").strip(),
                lat=_number(data.get("lat")), lon=_number(data.get("lon")),
                gumtree_area=data.get("gumtree_area", "").strip() or None,
                facebook_area=data.get("facebook_area", "").strip() or None)
    spec.save_home(_profile_name(data), home)


def save_hunt(data: dict) -> Hunt:
    size = {}
    for line in _lines(data.get("size", "")):
        key, _, value = line.partition("=")
        if _number(value) is None:
            raise SpecError(f"Size line '{line}' needs a number, like width_max = 200.")
        size[key.strip()] = _number(value)
    hunt = Hunt(slug=data.get("slug", "").strip().lower(), name=data.get("name", "").strip(),
                searches=_lines(data.get("searches", "")), max_price=_number(data.get("max_price")) or 0,
                max_distance=_number(data.get("max_distance")) or 0, sites=data.get("sites", []),
                size=size, musts=_lines(data.get("musts", "")), active=bool(data.get("active")),
                gumtree_category=data.get("gumtree_category", "").strip() or None)
    spec.save_hunt(_profile_name(data), hunt)
    return hunt


def create_profile(data: dict) -> str:
    name = data.get("name", "").strip().lower()
    spec.create_profile(name, Home(postcode=data.get("postcode", "").strip(),
                                   gumtree_area=data.get("gumtree_area", "").strip() or None))
    return name


def _profile_name(data: dict) -> str:
    name = data.get("profile", "")
    if name not in spec.list_profiles():
        raise SpecError("Unknown profile.")
    return name


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _number(value) -> float | None:
    try:
        return float(value) if str(value).strip() else None
    except (TypeError, ValueError):
        return None


class _Handler(BaseHTTPRequestHandler):
    default_profile: str | None

    def do_GET(self):
        url = urlparse(self.path)
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        if url.path == "/":
            body = render(query.get("profile", self.default_profile), query.get("hunt", ""),
                          query.get("tab", "new"), query.get("edit", ""))
            return self._send(200, "text/html; charset=utf-8", body)
        if url.path == "/photo":
            return self._photo(query.get("u", ""))
        if url.path == "/api/status":
            return self._json(200, JOB.status())
        if url.path in ("/static/page.css", "/static/page.js"):
            kind = "text/css" if url.path.endswith("css") else "text/javascript"
            return self._send(200, kind, (STATIC / Path(url.path).name).read_text())
        self._send(404, "text/plain", "Not found")

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        try:
            self._json(200, self._post(urlparse(self.path).path, data))
        except SpecError as error:
            self._json(400, {"error": str(error)})

    def _post(self, path: str, data: dict) -> dict:
        if path == "/viewed":
            store_for(_profile_name(data)).set_viewed(data["hunt"], data["key"], bool(data["viewed"]))
            return {}
        if path == "/api/home":
            save_home(data)
            return {"message": "Saved."}
        if path == "/api/hunt":
            hunt = save_hunt(data)
            go = _link(data["profile"], hunt.slug)
            if data.get("then") == "search":
                started = JOB.start(data["profile"], hunt.slug)
                return {"message": "Saved. Searching…" if started else "Saved. A search is already running.",
                        "go": go}
            return {"message": "Saved.", "go": go}
        if path == "/api/hunt/delete":
            spec.delete_hunt(_profile_name(data), data.get("slug", ""))
            return {"go": _link(data["profile"])}
        if path == "/api/profile":
            name = create_profile(data)
            return {"go": _link(name, edit="new")}
        if path == "/api/search":
            started = JOB.start(_profile_name(data), data.get("hunt") or None)
            return {"message": "Searching…" if started else "A search is already running."}
        raise SpecError("Unknown action.")

    def _photo(self, url: str):
        """Photos are fetched here, not by the browser, so a broken local DNS doesn't hide them."""
        host = urlparse(url).hostname or ""
        if urlparse(url).scheme != "https" or not any(part in host for part in PHOTO_HOSTS):
            return self._send(400, "text/plain", "Not a listing photo")
        cached = PHOTO_CACHE / hashlib.sha1(url.encode()).hexdigest()
        if not cached.exists():
            try:
                data = net.fetch(url)
            except net.FetchError:
                return self._send(502, "text/plain", "Photo unavailable")
            PHOTO_CACHE.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(data)
        self._send(200, "image/jpeg", cached.read_bytes(), cache=True)

    def log_message(self, *args):
        pass

    def _json(self, status: int, data: dict):
        self._send(status, "application/json", json.dumps(data))

    def _send(self, status: int, kind: str, body: str | bytes, cache: bool = False):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        if cache:
            self.send_header("Cache-Control", "max-age=604800")
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode())
