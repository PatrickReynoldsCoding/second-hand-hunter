"""Distance in miles between home and a listing's postcode.

Uses postcodes.io (free, UK only). Home is looked up by its outward code only
(e.g. "CR0"), so the full home postcode never leaves this computer.
"""

import json
import math
from pathlib import Path
from urllib.parse import quote

from hunter import net
from hunter.spec import Home

API = "https://api.postcodes.io"
EARTH_RADIUS_MILES = 3958.8


class Geo:
    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self.cache: dict[str, list[float] | None] = (
            json.loads(cache_file.read_text()) if cache_file.exists() else {}
        )

    def home_point(self, home: Home) -> tuple[float, float] | None:
        if home.lat is not None and home.lon is not None:
            return home.lat, home.lon
        return self._lookup("outcodes", outward_code(home.postcode))

    def postcode_point(self, postcode: str) -> tuple[float, float] | None:
        return self._lookup("postcodes", postcode.replace(" ", "").upper())

    def place_point(self, place: str, near: tuple[float, float]) -> tuple[float, float] | None:
        """Many towns share a name (Croydon, Shirley...), so take the one nearest home."""
        town = place.split(",")[0].strip()
        key = f"places/{town.lower()}"
        if key not in self.cache:
            self.cache[key] = self._fetch_places(town)
            self._save()
        candidates = self.cache[key] or []
        return tuple(min(candidates, key=lambda point: haversine_miles(near, point))) if candidates else None

    def miles(self, home: Home, postcode: str | None, place: str | None = None) -> float | None:
        """Exact from the postcode, else rough from the town name."""
        start = self.home_point(home)
        if not start:
            return None
        end = self.postcode_point(postcode) if postcode else None
        if end is None and place:
            end = self.place_point(place, start)
        if not end:
            return None
        return round(haversine_miles(start, end), 1)

    def _lookup(self, kind: str, code: str) -> tuple[float, float] | None:
        key = f"{kind}/{code}"
        if key not in self.cache:
            self.cache[key] = self._fetch(key)
            self._save()
        point = self.cache[key]
        return tuple(point) if point else None

    def _save(self) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(self.cache))

    def _fetch(self, key: str) -> list[float] | None:
        result = self._get(f"{API}/{key}")
        return [result["latitude"], result["longitude"]] if result else None

    def _fetch_places(self, town: str) -> list[list[float]]:
        results = self._get(f"{API}/places?q={quote(town)}&limit=50") or []
        return [[place["latitude"], place["longitude"]] for place in results
                if place.get("name_1", "").lower() == town.lower()]

    def _get(self, url: str):
        try:
            return json.loads(net.fetch_text(url))["result"]
        except (net.FetchError, KeyError, ValueError):
            return None

def outward_code(postcode: str) -> str:
    compact = postcode.replace(" ", "").upper()
    return compact[:-3] if len(compact) > 4 else compact


def haversine_miles(start: tuple[float, float], end: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*start, *end))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))
