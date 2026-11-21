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
    is_trade integer not null default 0,
    primary key (key, hunt)
)
"""


RUNS_SCHEMA = """
create table if not exists runs (
    id integer primary key,
    finished_at text not null,
    summary text not null
)
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute(SCHEMA)
        self.db.execute(RUNS_SCHEMA)
        columns = {row["name"] for row in self.db.execute("pragma table_info(listings)")}
        if "is_trade" not in columns:
            self.db.execute("alter table listings add column is_trade integer not null default 0")

    def known(self, hunt: str, key: str) -> bool:
        row = self.db.execute("select 1 from listings where hunt=? and key=?", (hunt, key)).fetchone()
        return row is not None

    def save(self, hunt: str, listing: Listing, miles: float | None, verdict: str,
             reason: str, seller_question: str = "") -> None:
        self.db.execute(
            "insert or replace into listings (key, hunt, site, url, title, price, description,"
            " image_urls, place, postcode, miles, age, verdict, reason, seller_question, found_at,"
            " is_trade) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,coalesce((select found_at from"
            " listings where key=? and hunt=?), ?),?)",
            (listing.key, hunt, listing.site, listing.url, listing.title, listing.price,
             listing.description, json.dumps(listing.image_urls), listing.place, listing.postcode,
             miles, listing.age, verdict, reason, seller_question, listing.key, hunt, _now(),
             int(listing.is_trade)),
        )
        self.db.commit()

    def listings(self, hunt: str) -> list[dict]:
        rows = self.db.execute(
            "select * from listings where hunt=? order by found_at desc", (hunt,)
        ).fetchall()
        return [{**row, "image_urls": json.loads(row["image_urls"] or "[]")} for row in rows]

    def unviewed(self, hunt: str) -> list[Listing]:
        rows = self.db.execute(
            "select * from listings where hunt=? and viewed_at is null", (hunt,)
        ).fetchall()
        return [
            Listing(site=row["site"], site_id=row["key"].split(":", 1)[1], url=row["url"],
                    title=row["title"], price=row["price"], description=row["description"] or "",
                    image_urls=json.loads(row["image_urls"] or "[]"), postcode=row["postcode"],
                    place=row["place"], age=row["age"], is_trade=bool(row["is_trade"]))
            for row in rows
        ]

    def save_run(self, summary: dict) -> None:
        self.db.execute("insert into runs (finished_at, summary) values (?, ?)", (_now(), json.dumps(summary)))
        self.db.commit()

    def recent_runs(self, limit: int = 5) -> list[dict]:
        rows = self.db.execute("select finished_at, summary from runs order by id desc limit ?", (limit,))
        return [{"finished_at": row["finished_at"], **json.loads(row["summary"])} for row in rows]

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
