"""AI-written summaries of what changed, kept in a file the page reads.

The page never calls an AI. When someone asks for it, the skill (in Claude Code or
Codex) reads what each commit or pull request changed, writes one plain line about
it, and a short digest of all of them grouped by topic, and saves them here with
`dashboard.py summarize --add`. Each commit is read only once. The daily build shows
the digest at the top of the Done tab, and each line, marked as written by AI, above
the commit's original message.

    # .github/dashboard/summaries.yaml
    commits:                       # full commit id -> what it changed
      "5870b546e597c333118e5e6d297e66f53e303605": "Labels the demo pages as made-up data"
    prs:                           # pull request number -> what it changed
      3: "Opens the demo on an overview of three repos, and rewrites the credits"
    digest:                        # what changed, grouped by topic; a new one replaces the old
      written: "2026-11-17"
      covers: "the last 40 commits, up to 445641b"
      groups:
        - title: "New tools, all off by default"
          items:
            - "Six helper tools: file search, calculator, date math, and more"
"""

import re
from typing import Any

import yaml

PATH = ".github/dashboard/summaries.yaml"
SHA = re.compile(r"^[0-9a-f]{40}$")
LONGEST = 200
DIGEST_LONGEST = 300
DIGEST_KEYS = {"written", "covers", "groups"}
HEADER = (
    "# What each commit or merged pull request changed, written by AI from its changes.\n"
    "# The page shows these marked as AI summaries, with the original message under them.\n"
    "# Add to it with `dashboard.py summarize --add`; fix a wrong line by hand.\n"
)


class SummariesError(ValueError):
    """The summaries file has a mistake. The message names what to fix."""


def _line(source: str, where: str, text: Any, longest: int = LONGEST) -> str:
    if not isinstance(text, str) or not text.strip() or "\n" in text.strip():
        raise SummariesError(f"{source}: {where}: a summary is one line of text")
    if len(text.strip()) > longest:
        raise SummariesError(f"{source}: {where}: keep a summary under {longest} characters")
    return text.strip()


def check(found: Any, source: str = "summaries") -> dict[str, dict]:
    """The summaries, checked: {"commits": {id: line}, "prs": {number: line}}, plus "digest" if there is one.

    Raises:
        SummariesError: naming the first mistake found.
    """
    if found is None:
        found = {}
    if not isinstance(found, dict) or set(found) - {"commits", "prs", "digest"}:
        raise SummariesError(f"{source}: the file has only `commits`, `prs`, and `digest`")
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
    if found.get("digest") is not None:
        out["digest"] = _digest(found["digest"], source)
    return out


def _digest(digest: Any, source: str) -> dict[str, Any]:
    """The digest, checked: when it was written, what it covers, and its groups of lines."""
    where = f"{source}: digest"
    if not isinstance(digest, dict) or set(digest) - DIGEST_KEYS or not digest.get("groups"):
        raise SummariesError(f"{where}: has `written`, `covers`, and a list of `groups`")
    for key in ("written", "covers"):
        if not isinstance(digest.get(key), str) or not digest[key].strip():
            raise SummariesError(f"{where}: give `{key}` as text")
    if not isinstance(digest["groups"], list):
        raise SummariesError(f"{where}: `groups` is a list")
    if len(digest["groups"]) > 12:
        raise SummariesError(f"{where}: keep it to 12 groups or fewer, so it stays short")
    groups = []
    for group in digest["groups"]:
        if not isinstance(group, dict) or set(group) != {"title", "items"} or not isinstance(group["items"], list) or not group["items"]:
            raise SummariesError(f"{where}: each group has a `title` and a list of `items`")
        title = _line(source, "digest group title", group["title"])
        items = [_line(source, f"digest, {title}", item, DIGEST_LONGEST) for item in group["items"]]
        groups.append({"title": title, "items": items})
    return {"written": digest["written"].strip(), "covers": digest["covers"].strip(), "groups": groups}


def load(text: str | None, source: str = "summaries") -> dict[str, dict]:
    """Parse and check the file's text. None (no file yet) means no summaries."""
    try:
        return check(yaml.safe_load(text) if text else None, source)
    except yaml.YAMLError as error:
        raise SummariesError(f"{source}: not valid YAML: {error}") from error


def merge(old: dict[str, dict], new: dict[str, dict]) -> dict[str, dict]:
    """The old summaries plus the new ones. A new line for the same id, or a new digest, replaces the old one."""
    merged = {"commits": {**old["commits"], **new["commits"]}, "prs": {**old["prs"], **new["prs"]}}
    digest = new.get("digest") or old.get("digest")
    return {**merged, "digest": digest} if digest else merged


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
