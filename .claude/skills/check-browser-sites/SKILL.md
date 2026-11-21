---
name: check-browser-sites
description: Check Facebook Marketplace and Preloved for second-hand-hunter, in the user's own Chrome (Claude in Chrome). Use when the user says "check Facebook", "check Preloved", "check the browser sites" or "check FB".
---

# Check Facebook / Preloved in the user's browser

These sites are only checked on request, in the user's own logged-in Chrome,
at a human pace. Never schedule this or run it unattended.

1. Load the Claude in Chrome tools and its skill. If they aren't available, tell
   the user in one line to run `/chrome` (or start Claude Code with `--chrome`) and stop.
2. Get the links: `python3 -m hunter links <profile>` (profile is the folder name in
   `profiles/`; there is usually one). Only open the sites the user asked for.
3. For each link: open it in a new tab, wait for listings, scroll once or twice.
   If filters didn't apply (price, distance), set them on the page.
4. For each listing whose title fits the hunt and price is under the max:
   open it, read title, price, town/area, full description and up to 5 photo URLs.
   Skip trade sellers and anything clearly not the item.
5. Add it (repeats are skipped automatically):
   ```sh
   python3 -m hunter add <profile> <hunt> --site facebook|preloved --url <listing url without tracking params> \
     --title "..." --price N --place "Town, Area" --description "..." --photo <url> --photo <url>
   ```
   Use the listing's canonical URL (e.g. `https://www.facebook.com/marketplace/item/<id>/`).
6. Never message sellers, like, save or click anything that changes the account.
   If a login or security check appears, stop and tell the user.
7. Finish with one line: how many new listings were added, and how many fit.
