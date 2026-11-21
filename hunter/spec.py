"""Load a profile (home location) and its hunts (one spec per item)."""

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"
KNOWN_SITES = {"ebay", "gumtree", "preloved", "facebook"}
CHECK_MODES = ("basic", "thorough")
DEFAULT_STAGES = ["To contact", "Contacted seller", "Viewing arranged", "Bought", "Gone / no reply"]


@dataclass
class Home:
    postcode: str
    lat: float | None = None
    lon: float | None = None
    gumtree_area: str | None = None
    facebook_area: str | None = None


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
    avoid: list[str] = field(default_factory=list)
    active: bool = True
    check_mode: str = "basic"
    gumtree_category: str | None = None


@dataclass
class Profile:
    name: str
    home: Home
    hunts: list[Hunt]
    stages: list[str] = field(default_factory=lambda: list(DEFAULT_STAGES))


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
    return Profile(name=name, home=home, hunts=[load_hunt(path) for path in hunt_files],
                   stages=raw.get("stages") or list(DEFAULT_STAGES))


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
        avoid=raw.get("avoid", []),
        check_mode=raw.get("check_mode", "basic"),
        active=raw.get("active", True),
        gumtree_category=raw.get("gumtree", {}).get("category"),
    )


# --- Editing (used by the review page) ---

SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{0,40}$"


def list_profiles(profiles_dir: Path = PROFILES_DIR) -> list[str]:
    if not profiles_dir.exists():
        return []
    return sorted(path.parent.name for path in profiles_dir.glob("*/profile.toml"))


def create_profile(name: str, home: Home, profiles_dir: Path = PROFILES_DIR) -> None:
    _check_slug(name)
    folder = profiles_dir / name
    if folder.exists():
        raise SpecError(f"Profile {name} already exists.")
    (folder / "hunts").mkdir(parents=True)
    save_home(name, home, profiles_dir)


def save_home(profile: str, home: Home, profiles_dir: Path = PROFILES_DIR,
              stages: list[str] | None = None) -> None:
    if not home.postcode.strip():
        raise SpecError("Postcode is needed.")
    path = profiles_dir / profile / "profile.toml"
    if stages is None and path.exists():
        stages = tomllib.loads(path.read_text()).get("stages")
    top = _toml_lines({"stages": stages}) + "\n" if stages else ""
    values = {key: value for key, value in vars(home).items() if value not in (None, "")}
    path.write_text(top + "[home]\n" + _toml_lines(values))


def save_hunt(profile: str, hunt: Hunt, profiles_dir: Path = PROFILES_DIR) -> None:
    _check_slug(hunt.slug)
    unknown = set(hunt.sites) - KNOWN_SITES
    if unknown:
        raise SpecError(f"Unknown sites: {', '.join(sorted(unknown))}")
    if hunt.check_mode not in CHECK_MODES:
        raise SpecError(f"Check mode must be one of: {', '.join(CHECK_MODES)}")
    if not hunt.name.strip() or not hunt.searches:
        raise SpecError("A hunt needs a name and at least one search.")
    top = {"name": hunt.name, "active": hunt.active, "searches": hunt.searches,
           "max_price": hunt.max_price, "max_distance": hunt.max_distance, "sites": hunt.sites,
           "avoid": hunt.avoid, "check_mode": hunt.check_mode}
    text = _toml_lines(top)
    if hunt.size:
        text += "\n[size]\n" + _toml_lines(hunt.size)
    for rule in hunt.musts:
        text += "\n[[must]]\n" + _toml_lines({"rule": rule})
    if hunt.gumtree_category:
        text += "\n[gumtree]\n" + _toml_lines({"category": hunt.gumtree_category})
    path = profiles_dir / profile / "hunts" / f"{hunt.slug}.toml"
    path.write_text(text)
    load_hunt(path)  # proves it reads back


def delete_hunt(profile: str, slug: str, profiles_dir: Path = PROFILES_DIR) -> None:
    _check_slug(slug)
    (profiles_dir / profile / "hunts" / f"{slug}.toml").unlink(missing_ok=True)


def _check_slug(slug: str) -> None:
    import re
    if not re.match(SLUG_PATTERN, slug):
        raise SpecError(f"'{slug}': use lower-case letters, numbers and dashes only.")


def _toml_lines(values: dict) -> str:
    return "".join(f"{key} = {_toml_value(value)}\n" for key, value in values.items())


def _toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return f"{value:g}"
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    return json.dumps(str(value), ensure_ascii=False)
