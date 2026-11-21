"""The review page, served on this computer only (http://localhost:8765)."""

import hashlib
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from hunter import net
from hunter.spec import Profile
from hunter.store import DATA_DIR, Store

PORT = 8765
TABS = {"new": "To review", "viewed": "Viewed", "rejected": "Rejected"}
PHOTO_CACHE = DATA_DIR / "photos"
PHOTO_HOSTS = ("img.gumtree.com", "i.ebayimg.com", "scontent", "fbcdn.net", "preloved")
BADGES = {"fits": "✅ Fits", "unknown": "❓ Ask seller", "no": "❌ No"}


def serve(profile: Profile, store: Store, port: int = PORT) -> None:
    handler = type("Handler", (_Handler,), {"profile": profile, "store": store})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"Review page: http://localhost:{port}")
    server.serve_forever()


def in_tab(listing: dict, tab: str) -> bool:
    if listing["viewed_at"]:
        return tab == "viewed"
    if listing["verdict"] == "no":
        return tab == "rejected"
    return tab == "new"


def render(profile: Profile, store: Store, hunt_slug: str, tab: str) -> str:
    hunts = [hunt for hunt in profile.hunts if hunt.active] or profile.hunts
    hunt = next((h for h in hunts if h.slug == hunt_slug), hunts[0] if hunts else None)
    if hunt is None:
        return _page("<p>No hunts yet. Add a file to profiles/&lt;you&gt;/hunts/.</p>")
    listings = store.listings(hunt.slug)
    hunt_links = "".join(
        f'<a class="{"on" if h.slug == hunt.slug else ""}" href="/?hunt={h.slug}">{html.escape(h.name)}</a>'
        for h in hunts
    )
    tab_links = "".join(
        f'<a class="{"on" if key == tab else ""}" href="/?hunt={hunt.slug}&tab={key}">'
        f'{label} ({sum(in_tab(item, key) for item in listings)})</a>'
        for key, label in TABS.items()
    )
    shown = [item for item in listings if in_tab(item, tab)]
    shown.sort(key=lambda item: (item["verdict"] != "fits", item["found_at"]), reverse=False)
    cards = "".join(_card(hunt.slug, item) for item in shown) or "<p class='empty'>Nothing here.</p>"
    return _page(f'<nav class="hunts">{hunt_links}</nav><nav class="tabs">{tab_links}</nav>'
                 f'<main>{cards}</main>')


def _card(hunt: str, item: dict) -> str:
    esc = html.escape
    photo = item["image_urls"][0] if item["image_urls"] else ""
    image = f'<img src="/photo?u={quote(photo, safe="")}" alt="" loading="lazy">' if photo else '<div class="nophoto">No photo</div>'
    price = f"£{item['price']:g}" if item["price"] else "No price given"
    miles = f"{item['miles']} mi" if item["miles"] is not None else "distance unknown"
    place = esc(item["place"] or "")
    question = ""
    if item["seller_question"]:
        question = (f'<p class="ask">{esc(item["seller_question"])}</p>'
                    f'<button class="copy" data-text="{esc(item["seller_question"])}">Copy question</button>')
    viewed = bool(item["viewed_at"])
    button = "Not viewed" if viewed else "Mark viewed"
    return f"""<article class="{esc(item['verdict'])}">
  <a href="{esc(item['url'])}" target="_blank" rel="noopener">{image}</a>
  <div class="body">
    <span class="badge">{BADGES.get(item['verdict'], item['verdict'])}</span> <span class="site">{esc(item['site'])}</span>
    <h2><a href="{esc(item['url'])}" target="_blank" rel="noopener">{esc(item['title'])}</a></h2>
    <p class="facts"><b>{price}</b> · {miles} · {place}</p>
    <p class="reason">{esc(item['reason'] or '')}</p>
    {question}
    <button class="view" data-hunt="{esc(hunt)}" data-key="{esc(item['key'])}" data-viewed="{int(not viewed)}">{button}</button>
  </div>
</article>"""


def _page(content: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Second-hand hunter</title>
<style>
:root{{--bg:#f7f6f3;--card:#fff;--ink:#222;--muted:#666;--line:#ddd;--accent:#2457c5;--fits:#1b7f3b;--unknown:#a86400;--no:#a33}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16171a;--card:#212328;--ink:#eee;--muted:#aaa;--line:#3a3d44;--accent:#7aa2ff;--fits:#5fd38a;--unknown:#f0b44c;--no:#f07a7a}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 system-ui,sans-serif}}
nav{{display:flex;gap:8px;flex-wrap:wrap;padding:12px 16px 0}}
nav a{{padding:6px 12px;border:1px solid var(--line);border-radius:999px;color:var(--ink);text-decoration:none}}
nav a.on{{background:var(--accent);border-color:var(--accent);color:#fff}}
main{{display:grid;gap:16px;padding:16px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr))}}
article{{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}}
article img,.nophoto{{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;background:var(--line)}}
.nophoto{{display:grid;place-items:center;color:var(--muted)}}
.body{{padding:12px 14px 14px;display:flex;flex-direction:column;gap:6px;flex:1}}
h2{{font-size:17px;margin:0}} h2 a{{color:var(--ink)}}
p{{margin:0}} .facts{{color:var(--muted)}} .reason{{font-size:14px}}
.badge{{font-weight:600}} .fits .badge{{color:var(--fits)}} .unknown .badge{{color:var(--unknown)}} .no .badge{{color:var(--no)}}
.site{{color:var(--muted);font-size:13px}}
.ask{{font-size:14px;border-left:3px solid var(--unknown);padding-left:8px}}
button{{font:inherit;padding:8px 12px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer}}
button.view{{margin-top:auto;background:var(--accent);border-color:var(--accent);color:#fff}}
.empty{{color:var(--muted)}}
</style></head><body>{content}
<script>
document.addEventListener('click', async e => {{
  const b = e.target.closest('button'); if (!b) return;
  if (b.classList.contains('copy')) {{ await navigator.clipboard.writeText(b.dataset.text); b.textContent = 'Copied'; return; }}
  if (b.classList.contains('view')) {{
    await fetch('/viewed', {{method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{hunt:b.dataset.hunt, key:b.dataset.key, viewed:b.dataset.viewed==='1'}})}});
    b.closest('article').remove();
  }}
}});
</script></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    profile: Profile
    store: Store

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        if urlparse(self.path).path == "/photo":
            return self._photo(query.get("u", [""])[0])
        if urlparse(self.path).path != "/":
            return self._send(404, "text/plain", "Not found")
        body = render(self.profile, self.store, query.get("hunt", [""])[0], query.get("tab", ["new"])[0])
        self._send(200, "text/html; charset=utf-8", body)

    def do_POST(self):
        if self.path != "/viewed":
            return self._send(404, "text/plain", "Not found")
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        self.store.set_viewed(data["hunt"], data["key"], bool(data["viewed"]))
        self._send(204, "text/plain", "")

    def log_message(self, *args):
        pass

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

    def _send(self, status: int, kind: str, body: str | bytes, cache: bool = False):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        if cache:
            self.send_header("Cache-Control", "max-age=604800")
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode())
