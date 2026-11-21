"""Claude usage: tokens per check, and % of the 5-hour and weekly plan limits.

The limits come from the same place Claude Code's /usage reads them. That
endpoint isn't documented, so any failure just means "unknown". The login
token is read from Claude Code's own credentials file and sent only to Anthropic.
"""

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

CREDENTIALS = Path.home() / ".claude" / ".credentials.json"
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
TOKEN_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


@dataclass
class Tally:
    checks: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    by_kind: dict[str, int] = field(default_factory=dict)

    def add(self, claude_output: dict) -> None:
        usage = claude_output.get("usage") or {}
        self.checks += 1
        for kind in TOKEN_FIELDS:
            count = int(usage.get(kind) or 0)
            self.tokens += count
            self.by_kind[kind] = self.by_kind.get(kind, 0) + count
        self.cost_usd += float(claude_output.get("total_cost_usd") or 0)


def limits() -> dict[str, float] | None:
    """{"five_hour": %, "seven_day": %}, or None if unavailable."""
    try:
        token = json.loads(CREDENTIALS.read_text())["claudeAiOauth"]["accessToken"]
        result = subprocess.run(
            ["curl", "-sSf", "--max-time", "15", USAGE_URL, "-H", f"Authorization: Bearer {token}",
             "-H", "anthropic-beta: oauth-2025-04-20"],
            capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        return {window: float(data[window]["utilization"]) for window in ("five_hour", "seven_day")}
    except (OSError, KeyError, TypeError, ValueError):
        return None
