# second-hand-hunter

Searches second-hand sites every morning for items that match a spec you write,
and gives you one page to review them and mark them as viewed.

- **A hunt** is one spec file: search words, max price, max distance, size limits,
  and must-haves in plain English. Any item works (sofa, bike, desk...).
- **Each listing** gets ✅ fits, ❓ ask seller (with a ready-made question) or ❌ no,
  with a one-line reason. Claude (headless Claude Code) reads the text and photos.
- **Distance** comes from the listing's postcode, or its town name if hidden.

## Sites

| Site | How |
| --- | --- |
| Gumtree | Daily. Reads the first page (30 newest/relevant) of the category in your area, plus each new listing. Gumtree's robots.txt blocks search pages and page 2+, so those aren't used. |
| eBay | Coming: needs a free developer key. |
| Facebook Marketplace | On request: say "check Facebook" in Claude Code (with Claude in Chrome) in this repo. Not automated, to keep your account safe. |
| Preloved | On request: "check Preloved". Its robots.txt blocks automated search. |

## Your info stays local

`profiles/` (your postcode and hunts) and `data/` (listings, viewed marks) are
gitignored. Home distance uses only the outward code (e.g. "CR0") with
postcodes.io, unless you put your own lat/lon in the profile.

## Set up

```sh
mkdir -p profiles/<you> && cp -r examples/* profiles/<you>/
# edit profiles/<you>/profile.toml and profiles/<you>/hunts/*.toml
python3 -m hunter run <you>      # search now
python3 -m hunter serve          # review page at http://localhost:8765
systemd/install.sh <you>         # daily 07:30 search + always-on review page
```

Needs Python 3.11+, curl, and Claude Code (`claude`) logged in.

## The review page

The sidebar picks the profile and hunt, edits the home details and each hunt's spec,
adds new profiles and hunts, and has "Save and re-check" (re-checks unviewed
listings against the edited spec, then searches for new ones). Each hunt has its
own "Search this hunt" button, with a check mode: **Basic** (Haiku, 3 photos) or
**Thorough** (Opus, 5 photos, more effort). Both start Claude with nothing extra
loaded, about 8k tokens per listing. The daily search uses each hunt's own mode. Recent searches show Claude tokens used and the
change in your 5-hour and weekly plan usage (read the same way as `/usage`;
undocumented, so it can show "unknown").

## Add a listing by hand

```sh
python3 -m hunter add <you> sofa --url <link> --title "Grey corner sofa" \
  --price 60 --place "Shirley, London" --description "..." --photo <photo-url>
```
