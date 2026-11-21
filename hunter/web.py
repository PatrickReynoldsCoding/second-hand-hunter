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
from hunter.store import DATA_DIR, STATUSES, store_for

PORT = 8765
STATIC = Path(__file__).resolve().parent / "static"
TABS = {"new": "To review", "interested": "Interested", "viewed": "Viewed", "rejected": "Rejected"}
BROWSER_SITES = {"facebook": "Facebook", "preloved": "Preloved"}
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
    if listing["status"]:
        return tab == listing["status"]
    if listing["verdict"] == "no":
        return tab == "rejected"
    return tab == "new"


# --- Searching in the background ---

class SearchJob:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.message = ""

    def start(self, profile_name: str, hunt_slug: str | None, recheck: bool = False,
              mode: str | None = None) -> bool:
        return self._launch("Searching…", self._run, profile_name, hunt_slug, recheck, mode)

    def start_browser(self, profile_name: str, site: str, hunt_slug: str | None, mode: str | None) -> bool:
        label = BROWSER_SITES.get(site, site)
        return self._launch(f"Claude is checking {label} in your Chrome…", self._run_browser,
                            profile_name, site, hunt_slug, mode or "basic")

    def _launch(self, message: str, target, *args) -> bool:
        with self.lock:
            if self.running:
                return False
            self.running, self.message = True, message
        threading.Thread(target=target, args=args, daemon=True).start()
        return True

    def _run_browser(self, profile_name: str, site: str, hunt_slug: str | None, mode: str) -> None:
        try:
            profile = spec.load_profile(profile_name)
            summary = run.run_browser_site(profile, store_for(profile_name), site, hunt_slug, mode)
            self.message = f"{BROWSER_SITES.get(site, site)}: {summary['found']} new. {usage_line(summary)}"
        except Exception as error:
            self.message = f"{site} check failed: {error}"
        finally:
            self.running = False

    def status(self) -> dict:
        return {"running": self.running, "message": self.message}

    def _run(self, profile_name: str, hunt_slug: str | None, recheck: bool, mode: str | None) -> None:
        try:
            profile = spec.load_profile(profile_name)
            summary = run.run_profile(profile, store_for(profile_name), hunt_slug, recheck,
                                      on_progress=self._progress, mode=mode)
            self.message = (f"Done: {summary['found']} new, {summary['rechecked']} re-checked. "
                            f"{usage_line(summary)}")
        except Exception as error:
            self.message = f"Search failed: {error}"
        finally:
            self.running = False

    def _progress(self, message: str) -> None:
        self.message = message


def usage_line(summary: dict) -> str:
    site = f"{BROWSER_SITES.get(summary['site'], summary['site'])} " if summary.get("site") else ""
    mode = f"{site}{summary['mode']}: " if summary.get("mode") else ""
    tokens = f"{mode}{summary['tokens']:,} tokens ({summary['checks']} Claude checks)"
    before, after = summary.get("limits_before"), summary.get("limits_after")
    if not before or not after:
        return tokens + ", plan % unknown"
    windows = {"five_hour": "5-hour", "seven_day": "week"}
    parts = [f"{label} +{after[key] - before[key]:g}% (now {after[key]:g}%)" for key, label in windows.items()]
    return f"{tokens}, {', '.join(parts)}"


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
    if tab == "interested":
        body = _interested(profile, hunt.slug, shown)
    else:
        cards = "".join(_card(profile.name, hunt.slug, item, tab) for item in shown)
        body = f'<div class="cards">{cards or "<p class=empty>Nothing here.</p>"}</div>'
    browser_buttons = "".join(
        f'<button type="button" data-browser="{site}" data-hunt="{html.escape(hunt.slug)}">'
        f'Get Claude to check {label}</button>'
        for site, label in BROWSER_SITES.items() if site in hunt.sites)
    header = (f'<header><h1>{html.escape(hunt.name)}</h1><div class="buttons">{_mode_picker()}'
              f'<button type="button" class="primary" data-search="{html.escape(hunt.slug)}">'
              f'Search this hunt</button>{browser_buttons}</div></header>')
    return _page(sidebar, f'{header}<nav class="tabs">{tab_links}</nav>{body}')


def _interested(profile: Profile, hunt: str, items: list[dict]) -> str:
    """Interested listings grouped by stage (e.g. "Contacted seller")."""
    stages = list(profile.stages)
    stages += [item["stage"] for item in items if item["stage"] and item["stage"] not in stages]
    sections = []
    for stage in stages:
        in_stage = [item for item in items if (item["stage"] or stages[0]) == stage]
        cards = "".join(_card(profile.name, hunt, item, "interested", stages) for item in in_stage)
        sections.append(f'<section class="stage"><h2>{html.escape(stage)} ({len(in_stage)})</h2>'
                        f'<div class="cards">{cards or "<p class=empty>None.</p>"}</div></section>')
    return "".join(sections)


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
        parts.append(f"""<section><h2>Searches</h2>
  {_mode_picker()}<button type="button" data-search="">Search all hunts</button>
  {"".join(f'<button type="button" data-browser="{site}" data-hunt="">Get Claude to check {label} (all hunts)</button>'
           for site, label in BROWSER_SITES.items()
           if any(site in h.sites for h in profile.hunts))}
  <p id="status" class="muted"></p>{_recent_runs(profile.name)}</section>""")
    return "".join(parts)


def _mode_picker() -> str:
    return ('<label class="row">Check <select class="mode-pick" title="Basic: fast and cheap. '
            'Thorough: strongest model, more photos, several times the tokens.">'
            '<option value="basic">Basic</option><option value="thorough">Thorough</option></select></label>')


def _recent_runs(profile: str) -> str:
    runs = store_for(profile).recent_runs()
    if not runs:
        return ""
    rows = "".join(
        f'<li><b>{run_info["finished_at"][5:16].replace("T", " ")}</b> · {html.escape(", ".join(run_info["hunts"]))} · '
        f'{run_info["found"]} new<br><span class="muted">{html.escape(usage_line(run_info))}</span>'
        + (f'<details><summary>Claude\'s report</summary><p>{html.escape(run_info["result"])}</p></details>'
           if run_info.get("result") else "") + '</li>'
        for run_info in runs)
    return f'<ul class="runs">{rows}</ul>'


def _home_form(profile: Profile) -> str:
    home = profile.home
    fields = [("postcode", "Postcode", home.postcode), ("gumtree_area", "Gumtree area", home.gumtree_area),
              ("facebook_area", "Facebook area", home.facebook_area),
              ("lat", "Latitude (optional)", home.lat), ("lon", "Longitude (optional)", home.lon)]
    return f"""<details><summary>Profile: {html.escape(home.postcode)}, stages</summary>
<form class="api" data-api="/api/home" data-profile="{html.escape(profile.name)}">
  {"".join(_input(name, label, value) for name, label, value in fields)}
  {_textarea("stages", "Interested stages (one per line)", chr(10).join(profile.stages))}
  <button>Save</button>
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
  {_textarea("avoid", "Don't want (one per line, e.g. leather)", "\n".join(h.avoid))}
  {_input("gumtree_category", "Gumtree category path", h.gumtree_category)}
  <label>Daily search check<select name="check_mode">{"".join(
      f'<option value="{m}" {"selected" if m == h.check_mode else ""}>{m.title()}</option>'
      for m in spec.CHECK_MODES)}</select></label>
  <div class="buttons"><button name="then" value="">Save</button>
  <button name="then" value="search" class="primary">Save and re-check</button>{delete}</div>
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


ACTIONS = {
    "new": [("interested", "Interested"), ("viewed", "Viewed"), ("rejected", "Reject")],
    "viewed": [("interested", "Interested"), ("rejected", "Reject"), ("", "Back to review")],
    "rejected": [("interested", "Interested"), ("", "Back to review")],
    "interested": [("rejected", "Reject"), ("", "Back to review")],
}


def _card(profile: str, hunt: str, item: dict, tab: str, stages: list[str] | None = None) -> str:
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
    ids = f'data-profile="{esc(profile)}" data-hunt="{esc(hunt)}" data-key="{esc(item["key"])}"'
    stage_pick = ""
    if stages:
        current = item["stage"] or stages[0]
        options = "".join(f'<option {"selected" if stage == current else ""}>{esc(stage)}</option>'
                          for stage in stages)
        stage_pick = f'<label>Stage<select class="stage-pick" {ids}>{options}</select></label>'
    buttons = "".join(
        f'<button type="button" class="status {"primary" if status == "interested" else ""}" {ids} '
        f'data-status="{status}">{label}</button>' for status, label in ACTIONS.get(tab, ACTIONS["new"]))
    return f"""<article class="{esc(item['verdict'])}">
  <a href="{esc(item['url'])}" target="_blank" rel="noopener">{image}</a>
  <div class="body">
    <span class="badge">{BADGES.get(item['verdict'], item['verdict'])}</span> <span class="muted">{esc(item['site'])}</span>
    <h3><a href="{esc(item['url'])}" target="_blank" rel="noopener">{esc(item['title'])}</a></h3>
    <p class="muted"><b>{price}</b> · {miles} · {esc(item['place'] or '')}</p>
    <p class="reason">{esc(item['reason'] or '')}</p>
    {question}{stage_pick}
    <div class="buttons actions">{buttons}</div>
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
    spec.save_home(_profile_name(data), home, stages=_lines(data.get("stages", "")) or None)


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
                size=size, musts=_lines(data.get("musts", "")), avoid=_lines(data.get("avoid", "")),
                active=bool(data.get("active")), check_mode=data.get("check_mode", "basic"),
                gumtree_category=data.get("gumtree_category", "").strip() or None)
    spec.save_hunt(_profile_name(data), hunt)
    return hunt


def create_profile(data: dict) -> str:
    name = data.get("name", "").strip().lower()
    spec.create_profile(name, Home(postcode=data.get("postcode", "").strip(),
                                   gumtree_area=data.get("gumtree_area", "").strip() or None))
    return name


def _mode(data: dict) -> str | None:
    mode = data.get("mode")
    return mode if mode in spec.CHECK_MODES else None


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
        if path == "/api/status":
            status = data.get("status") or None
            if status is not None and status not in STATUSES:
                raise SpecError("Unknown status.")
            store_for(_profile_name(data)).set_status(data["hunt"], data["key"], status, data.get("stage"))
            return {}
        if path == "/api/browser":
            if data.get("site") not in BROWSER_SITES:
                raise SpecError("Unknown site.")
            started = JOB.start_browser(_profile_name(data), data["site"], data.get("hunt") or None, _mode(data))
            label = BROWSER_SITES[data["site"]]
            return {"message": f"Claude is checking {label}. Keep Chrome open." if started
                    else "Something is already running."}
        if path == "/api/home":
            save_home(data)
            return {"message": "Saved."}
        if path == "/api/hunt":
            hunt = save_hunt(data)
            go = _link(data["profile"], hunt.slug)
            if data.get("then") == "search":
                started = JOB.start(data["profile"], hunt.slug, recheck=True, mode=_mode(data))
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
            started = JOB.start(_profile_name(data), data.get("hunt") or None, mode=_mode(data))
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
