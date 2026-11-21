"""Polite web fetching: one request at a time, a pause between them.

Uses curl so a broken local DNS can fall back to a public DNS-over-HTTPS lookup.
"""

import subprocess
import time

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) second-hand-hunter/0.1"
PAUSE_SECONDS = 3
CURL_COULD_NOT_RESOLVE = 6
FALLBACK_DNS = "https://1.1.1.1/dns-query"

_last_request = 0.0


class FetchError(RuntimeError):
    pass


def fetch(url: str, timeout: int = 30) -> bytes:
    _wait_turn()
    result = _curl(url, timeout)
    if result.returncode == CURL_COULD_NOT_RESOLVE:
        result = _curl(url, timeout, "--doh-url", FALLBACK_DNS)
    if result.returncode != 0:
        raise FetchError(f"{url}: curl exit {result.returncode} {result.stderr.decode().strip()}")
    return result.stdout


def fetch_text(url: str) -> str:
    return fetch(url).decode("utf-8", errors="replace")


def _curl(url: str, timeout: int, *extra: str) -> subprocess.CompletedProcess:
    command = ["curl", "-sSfL", "--max-time", str(timeout), "-A", USER_AGENT, *extra, url]
    return subprocess.run(command, capture_output=True)


def _wait_turn() -> None:
    global _last_request
    wait = _last_request + PAUSE_SECONDS - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()
