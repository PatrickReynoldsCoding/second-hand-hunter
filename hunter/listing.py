"""A listing found on any site, in one shape."""

from dataclasses import dataclass, field


@dataclass
class Listing:
    site: str
    site_id: str
    url: str
    title: str
    price: float | None
    description: str = ""
    image_urls: list[str] = field(default_factory=list)
    postcode: str | None = None
    place: str | None = None
    age: str | None = None
    is_trade: bool = False

    @property
    def key(self) -> str:
        return f"{self.site}:{self.site_id}"
