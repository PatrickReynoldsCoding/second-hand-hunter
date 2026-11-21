"""Start a background Claude that checks a site in your own Chrome (Claude in Chrome).

Used for sites that can't be searched automatically (Facebook, Preloved). It
follows .claude/skills/check-browser-sites and adds listings with `hunter add`.
Chrome must be open with the Claude extension.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from hunter.usage import Tally

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / ".claude" / "skills" / "check-browser-sites" / "SKILL.md"
TIMEOUT_SECONDS = 20 * 60
BROWSE_MODEL = {"basic": "sonnet", "thorough": "opus"}
ALLOWED_TOOLS = ["mcp__claude-in-chrome__*", "Bash(python3 -m hunter add:*)",
                 "Bash(python3 -m hunter links:*)"]
# Load nothing Claude doesn't need (plugins, skills, memory, other MCP servers):
# every browsing step re-reads all of it, so it multiplies the token cost.
LEAN_FLAGS = ["--setting-sources", "project", "--disable-slash-commands", "--strict-mcp-config"]


def prompt(profile: str, site: str, hunt: str | None, mode: str) -> str:
    which = f"only the hunt '{hunt}'" if hunt else "every active hunt"
    instructions = SKILL.read_text().split("---", 2)[-1]
    return (f"Follow these instructions.\n{instructions}\n\nThis run: profile {profile}, site {site} only, "
            f"{which}. Add listings with `--mode {mode}`. Save tokens: read pages with get_page_text "
            "or find, not screenshots, and don't open listings that clearly don't fit. "
            "End with a short report: listings seen, added, and why others were skipped.")


def run(profile: str, site: str, hunt: str | None, mode: str, tally: Tally) -> str:
    """Runs to the end and returns Claude's one-line summary. Adds tokens to the tally."""
    with tempfile.NamedTemporaryFile("r", suffix=".jsonl") as usage_file:
        env = {**os.environ, "HUNTER_USAGE_FILE": usage_file.name}
        command = ["claude", "-p", prompt(profile, site, hunt, mode), "--chrome", *LEAN_FLAGS,
                   "--model", BROWSE_MODEL.get(mode, "sonnet"), "--output-format", "json",
                   "--no-session-persistence", "--allowedTools", *ALLOWED_TOOLS]
        try:
            result = subprocess.run(command, capture_output=True, text=True, cwd=REPO, env=env,
                                    timeout=TIMEOUT_SECONDS, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return f"Stopped: the {site} check took over {TIMEOUT_SECONDS // 60} minutes."
        for line in Path(usage_file.name).read_text().splitlines():
            tally.add(json.loads(line))
    try:
        output = json.loads(result.stdout)
    except ValueError:
        return f"Claude didn't finish: {result.stderr.strip()[:200]}"
    tally.add(output)
    return str(output.get("result") or "Done.").strip()[:1500]
