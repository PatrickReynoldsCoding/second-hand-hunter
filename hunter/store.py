"""Listings found, their verdicts and viewed marks, in data/<profile>.db."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from hunter.listing import Listing

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SCHEMA = """
create table if not exists listings (
    key text not null,
    hunt text not null,
    site text not null,
    url text not null,
    title text not null,
    price real,
    description text,
    image_urls text,
    place text,
    postcode text,
    miles real,
    age text,
    verdict text not null,
    reason text,
    seller_question text,
    found_at text not null,
    viewed_at text,
    primary key (key, hunt)
)
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute(SCHEMA)

    def known(self, hunt: str, key: str) -> bool:
        row = self.db.execute("select 1 from listings where hunt=? and key=?", (hunt, key)).fetchone()
        return row is not None

    def save(self, hunt: str, listing: Listing, miles: float | None, verdict: str,
             reason: str, seller_question: str = "") -> None:
        self.db.execute(
            "insert or replace into listings values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,null)",
            (listing.key, hunt, listing.site, listing.url, listing.title, listing.price,
             listing.description, json.dumps(listing.image_urls), listing.place, listing.postcode,
             miles, listing.age, verdict, reason, seller_question, _now()),
        )
        self.db.commit()

    def listings(self, hunt: str) -> list[dict]:
        rows = self.db.execute(
            "select * from listings where hunt=? order by found_at desc", (hunt,)
        ).fetchall()
        return [{**row, "image_urls": json.loads(row["image_urls"] or "[]")} for row in rows]

    def set_viewed(self, hunt: str, key: str, viewed: bool) -> None:
        self.db.execute(
            "update listings set viewed_at=? where hunt=? and key=?",
            (_now() if viewed else None, hunt, key),
        )
        self.db.commit()


def store_for(profile: str) -> Store:
    return Store(DATA_DIR / f"{profile}.db")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
