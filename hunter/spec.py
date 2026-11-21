"""Load a profile (home location) and its hunts (one spec per item)."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"
KNOWN_SITES = {"ebay", "gumtree", "preloved", "facebook"}


@dataclass
class Home:
    postcode: str
    lat: float | None = None
    lon: float | None = None
    gumtree_area: str | None = None


@dataclass
class Hunt:
    slug: str
    name: str
    searches: list[str]
    max_price: float
    max_distance: float
    sites: list[str]
    size: dict[str, float] = field(default_factory=dict)
    musts: list[str] = field(default_factory=list)
    active: bool = True
    gumtree_category: str | None = None


@dataclass
class Profile:
    name: str
    home: Home
    hunts: list[Hunt]


class SpecError(ValueError):
    pass


def load_profile(name: str, profiles_dir: Path = PROFILES_DIR) -> Profile:
    folder = profiles_dir / name
    profile_file = folder / "profile.toml"
    if not profile_file.exists():
        raise SpecError(f"No profile at {profile_file}. Copy examples/ there first.")
    raw = tomllib.loads(profile_file.read_text())
    home = Home(**raw["home"])
    hunt_files = sorted((folder / "hunts").glob("*.toml"))
    return Profile(name=name, home=home, hunts=[load_hunt(path) for path in hunt_files])


def load_hunt(path: Path) -> Hunt:
    raw = tomllib.loads(path.read_text())
    missing = {"name", "searches", "max_price", "max_distance"} - raw.keys()
    if missing:
        raise SpecError(f"{path.name} is missing: {', '.join(sorted(missing))}")
    sites = raw.get("sites", ["ebay", "gumtree", "preloved"])
    unknown = set(sites) - KNOWN_SITES
    if unknown:
        raise SpecError(f"{path.name} has unknown sites: {', '.join(sorted(unknown))}")
    return Hunt(
        slug=path.stem,
        name=raw["name"],
        searches=raw["searches"],
        max_price=raw["max_price"],
        max_distance=raw["max_distance"],
        sites=sites,
        size=raw.get("size", {}),
        musts=[must["rule"] for must in raw.get("must", [])],
        active=raw.get("active", True),
        gumtree_category=raw.get("gumtree", {}).get("category"),
    )
