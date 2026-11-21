"""eBay: waiting for a developer key. Returns nothing until one is set up."""

import logging

from hunter.listing import Listing
from hunter.spec import Hunt, Home

log = logging.getLogger("hunter")


def ready() -> bool:
    return False


def search(hunt: Hunt, home: Home) -> list[Listing]:
    log.info("eBay skipped: no developer key yet.")
    return []
