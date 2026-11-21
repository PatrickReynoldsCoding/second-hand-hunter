"""Commands:

  python -m hunter run   <profile>             search all sites now
  python -m hunter serve <profile>             open the review page
  python -m hunter add   <profile> <hunt> ...  add a listing by hand (e.g. Facebook)
  python -m hunter links <profile>             search links for sites checked in a browser
"""

import argparse
import logging

from hunter import links, run, web
from hunter.geo import Geo
from hunter.listing import Listing
from hunter.spec import load_profile
from hunter.store import DATA_DIR, store_for


def main() -> None:
    parser = argparse.ArgumentParser(prog="hunter")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "links"):
        commands.add_parser(name).add_argument("profile")
    commands.add_parser("serve").add_argument("profile", nargs="?")
    add = commands.add_parser("add", help="add a listing found by hand")
    add.add_argument("profile")
    add.add_argument("hunt")
    add.add_argument("--site", default="facebook")
    add.add_argument("--url", required=True)
    add.add_argument("--title", required=True)
    add.add_argument("--price", type=float)
    add.add_argument("--postcode")
    add.add_argument("--place")
    add.add_argument("--description", default="")
    add.add_argument("--photo", action="append", default=[], help="photo URL, can repeat")
    add.add_argument("--mode", choices=["rules", "basic", "thorough"], help="check mode (default: the hunt's)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if args.command == "serve":
        return web.serve(args.profile)
    profile = load_profile(args.profile)
    store = store_for(args.profile)

    if args.command == "run":
        summary = run.run_profile(profile, store)
        print(f"New listings: {summary['found']}. Claude checks: {summary['checks']}, "
              f"tokens: {summary['tokens']:,}. Limits before/after: "
              f"{summary['limits_before']} / {summary['limits_after']}")
    elif args.command == "links":
        for hunt in profile.hunts:
            for site, url in links.browser_search_urls(profile.home, hunt):
                print(f"{hunt.slug}\t{site}\t{url}")
    else:
        hunt = next(h for h in profile.hunts if h.slug == args.hunt)
        listing = Listing(
            site=args.site, site_id=args.url.rstrip("/").rsplit("/", 1)[-1], url=args.url,
            title=args.title, price=args.price, description=args.description,
            image_urls=args.photo, postcode=args.postcode, place=args.place,
        )
        if store.known(hunt.slug, listing.key):
            print("already have: skipped")
            return
        verdict = run.add_listing(profile, hunt, listing, store, Geo(DATA_DIR / "geo-cache.json"),
                                  fetch_details=False, mode=args.mode)
        print(f"{verdict.verdict}: {verdict.reason}")


if __name__ == "__main__":
    main()
