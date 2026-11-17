"""AI-written titles for commits and merged pull requests, kept in a file the page reads.

The page never calls an AI. When someone asks for it, the skill (in Claude Code or
Codex) reads what each commit or pull request changed, writes one plain line about
it, and saves the lines here with `dashboard.py summarize --add`. Each one is read
only once. The daily build then shows the line, marked as written by AI, above the
original message.

    # .github/dashboard/summaries.yaml
    commits:                       # full commit id -> what it changed
      "5870b546e597c333118e5e6d297e66f53e303605": "Labels the demo pages as made-up data"
    prs:                           # pull request number -> what it changed
      3: "Opens the demo on an overview of three repos, and rewrites the credits"
"""

import re
from typing import Any

import yaml

PATH = ".github/dashboard/summaries.yaml"
SHA = re.compile(r"^[0-9a-f]{40}$")
LONGEST = 200
HEADER = (
    "# What each commit or merged pull request changed, written by AI from its changes.\n"
    "# The page shows these marked as AI summaries, with the original message under them.\n"
    "# Add to it with `dashboard.py summarize --add`; fix a wrong line by hand.\n"
)


class SummariesError(ValueError):
    """The summaries file has a mistake. The message names what to fix."""


def _line(source: str, where: str, text: Any) -> str:
    if not isinstance(text, str) or not text.strip() or "\n" in text.strip():
        raise SummariesError(f"{source}: {where}: a summary is one line of text")
    if len(text.strip()) > LONGEST:
        raise SummariesError(f"{source}: {where}: keep a summary under {LONGEST} characters")
    return text.strip()


def check(found: Any, source: str = "summaries") -> dict[str, dict]:
    """The summaries, checked: {"commits": {id: line}, "prs": {number: line}}.

    Raises:
        SummariesError: naming the first mistake found.
    """
    if found is None:
        found = {}
    if not isinstance(found, dict) or set(found) - {"commits", "prs"}:
        raise SummariesError(f"{source}: the file has only `commits` and `prs`")
    commits, prs = found.get("commits") or {}, found.get("prs") or {}
    if not isinstance(commits, dict) or not isinstance(prs, dict):
        raise SummariesError(f"{source}: `commits` and `prs` each map an id to a line")
    out: dict[str, dict] = {"commits": {}, "prs": {}}
    for sha, text in commits.items():
        if not isinstance(sha, str) or not SHA.match(sha):
            raise SummariesError(f"{source}: {sha!r} is not a full commit id in quotes")
        out["commits"][sha] = _line(source, sha[:7], text)
    for number, text in prs.items():
        if isinstance(number, str) and number.isdigit():  # JSON keys are always text
            number = int(number)
        if type(number) is not int or number < 1:
            raise SummariesError(f"{source}: {number!r} is not a pull request number")
        out["prs"][number] = _line(source, f"#{number}", text)
    return out


def load(text: str | None, source: str = "summaries") -> dict[str, dict]:
    """Parse and check the file's text. None (no file yet) means no summaries."""
    try:
        return check(yaml.safe_load(text) if text else None, source)
    except yaml.YAMLError as error:
        raise SummariesError(f"{source}: not valid YAML: {error}") from error


def merge(old: dict[str, dict], new: dict[str, dict]) -> dict[str, dict]:
    """The old summaries plus the new ones. A new line for the same id replaces the old one."""
    return {"commits": {**old["commits"], **new["commits"]}, "prs": {**old["prs"], **new["prs"]}}


def dump(summaries: dict[str, dict]) -> str:
    """The file's text, with a note at the top saying what it is."""
    body = yaml.safe_dump(summaries, sort_keys=False, allow_unicode=True, width=1000)
    return HEADER + body


def todo(data: dict[str, Any], summaries: dict[str, dict]) -> list[dict[str, Any]]:
    """The commits and merged pull requests the page shows that have no summary yet.

    Each comes with the command that shows what it changed.
    """
    repo = data["repo"]
    out = [
        {"kind": "commit", "id": push["oid"], "message": push["title"],
         "read": f"git show --stat --patch {push['oid']}"}
        for push in data.get("pushes", [])
        if push["oid"] not in summaries["commits"]
    ]
    out += [
        {"kind": "pr", "id": pr["number"], "message": pr["title"],
         "read": f"gh pr diff {pr['number']} --repo {repo}"}
        for pr in data["closed_prs"]
        if pr["state"] == "MERGED" and pr["number"] not in summaries["prs"]
    ]
    return out


def find(data: dict[str, Any], item: dict[str, Any]) -> str | None:
    """The summary for a Done-tab item (a push or a pull request), if there is one."""
    summaries = data.get("summaries") or {}
    if item["kind"] == "push":
        return (summaries.get("commits") or {}).get(item["oid"])
    if item["kind"] == "pr":
        return (summaries.get("prs") or {}).get(item["number"])
    return None
