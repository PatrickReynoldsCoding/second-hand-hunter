# second-hand-hunter

Searches second-hand sites for items that match a spec you write, and gives you
one app window to review them. Searches only run when you press a button.

- **A hunt** is one spec file: search words, max price, max distance, size limits,
  and must-haves in plain English. Any item works (sofa, bike, desk...).
- **Each listing** gets ✅ fits, ❓ ask seller (with a ready-made question) or ❌ no,
  with a one-line reason.
- **Check modes:** **No AI** (text rules only: don't-want words and sizes written in
  the listing; no tokens), **Basic AI** and **Thorough AI** (Claude also reads the photos
  and the plain-English must-haves). The text rules always run first, so clear
  rejects never cost tokens.
- **Distance** comes from the listing's postcode, or its town name if hidden.

## Sites

| Site | How |
| --- | --- |
| Gumtree | When you press Search. Reads the first page (30 newest/relevant) of the category in your area, plus each new listing. Gumtree's robots.txt blocks search pages and page 2+, so those aren't used. |
| eBay | Coming: needs a free developer key. |
| Facebook Marketplace | On request: the "Get Claude to check Facebook" button starts a background Claude in your Chrome (Claude in Chrome). Never on a timer, to keep your account safe. |
| Preloved | On request, the same way. Its robots.txt blocks automated search. |

## Your info stays local

`profiles/` (your postcode and hunts) and `data/` (listings, viewed marks) are
gitignored. Home distance uses only the outward code (e.g. "CR0") with
postcodes.io, unless you put your own lat/lon in the profile.

## Set up

```sh
mkdir -p profiles/<you> && cp -r examples/* profiles/<you>/
# edit profiles/<you>/profile.toml and profiles/<you>/hunts/*.toml
app/install.sh                   # adds a "Second-hand Hunter" app icon (Linux, Chrome)
python3 -m hunter serve          # or: page at http://localhost:8765 in a browser
python3 -m hunter run <you>      # or: search from the terminal (No AI mode)
```

Needs Python 3.11+, curl, and Claude Code (`claude`) logged in.

## The review page

The sidebar picks the profile and hunt, edits the home details and each hunt's spec,
adds new profiles and hunts, and has "Save and re-check" (re-checks unviewed
listings against the edited spec, then searches for new ones). Each hunt has its
own "Search this hunt" button and a check-mode picker. AI modes start Claude with
nothing extra loaded (about 8k tokens per listing). Recent searches show Claude tokens used and the
change in your 5-hour and weekly plan usage (read the same way as `/usage`;
undocumented, so it can show "unknown").

Each listing can be marked **Interested**, **Viewed** or **Reject**. The
Interested tab groups listings by stage ("Contacted seller", "Viewing arranged"…);
edit the stages in the sidebar under Profile.

## Add a listing by hand

```sh
python3 -m hunter add <you> sofa --url <link> --title "Grey corner sofa" \
  --price 60 --place "Shirley, London" --description "..." --photo <photo-url>
```
