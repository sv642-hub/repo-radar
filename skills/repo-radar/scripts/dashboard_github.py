"""Ask GitHub for a repo's pull requests, issues, and releases, and sort them.

Everything goes through the GitHub CLI (`gh`), so it uses whoever is signed in on
this computer, or the GH_TOKEN a GitHub Action gives it. Nothing here calls an AI:
pull requests and issues are sorted by facts GitHub already has (draft, checks,
reviews, assignees, links).
"""

import json
import logging
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

logger = logging.getLogger(__name__)

OPEN_PR_FIELDS = (
    "number,title,state,author,url,isDraft,createdAt,updatedAt,baseRefName,headRefName,"
    "reviewDecision,statusCheckRollup,closingIssuesReferences,additions,deletions,"
    "changedFiles,labels,headRepository,headRepositoryOwner,isCrossRepository"
)
CLOSED_PR_FIELDS = "number,title,state,author,url,createdAt,closedAt,mergedAt,labels"
OPEN_ISSUE_FIELDS = (
    "id,number,title,state,author,url,createdAt,updatedAt,labels,assignees"
)
CLOSED_ISSUE_FIELDS = "number,title,state,stateReason,author,url,createdAt,closedAt,labels"
ONE_PR_FIELDS = "number,title,state,author,url,isDraft,headRefName,mergedAt,closedAt"

# The order here is the order on the page: what a person can act on first.
PR_GROUPS = {
    "ready": ("Ready to merge", "approved, and no check is failing"),
    "review": ("Needs review", "nobody has approved it or asked for changes yet"),
    "author": ("Waiting on the author", "a reviewer asked for changes"),
    "failing": ("Checks failing", "fix the failing check before anyone reviews it"),
    "draft": ("Draft", "the author says it is not ready yet"),
}
ISSUE_GROUPS = {
    "nobody": ("Nobody on it yet", "no one assigned and no pull request"),
    "assigned": ("Someone is on it", "assigned, but no pull request yet"),
    "pr": ("A pull request is open", "an open pull request says it closes this issue"),
}
FAILED = {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}


def _gh(args: list[str]) -> Any:
    """Run one gh command and return its JSON output."""
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def read_file(repo: str, path: str) -> str | None:
    """A file's text from a repo's default branch on GitHub, or None if there is no such file.

    GitHub answers "Not Found" both for a missing file and for a repo the token may not
    see, so on "Not Found" this checks the repo itself, to say which one it was.

    Raises:
        RuntimeError: if the repo cannot be seen, or GitHub fails another way.
    """
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/contents/{quote(path)}", "-H", "Accept: application/vnd.github.raw+json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout
    if "404" in result.stderr or "Not Found" in result.stderr:
        visible = subprocess.run(["gh", "api", f"repos/{repo}", "--silent"], capture_output=True, check=False)
        if visible.returncode != 0:
            raise RuntimeError(
                f"cannot see {repo}: it does not exist, or it is private and the token "
                "cannot read it (a watch list needs a RADAR_TOKEN secret for private repos)"
            )
        return None
    raise RuntimeError(f"reading {path} from {repo} failed: {result.stderr.strip()}")


def _listed(kind: str, state: str, fields: str, limit: int, repo: list[str], search: str = "") -> list:
    """`gh pr list` or `gh issue list`, with a warning when the limit cut the list short."""
    args = [kind, "list", *repo, "--state", state, "--limit", str(limit), "--json", fields]
    if search:
        args += ["--search", search]
    found = _gh(args)
    if len(found) >= limit:
        logger.warning(f"got {len(found)} {kind}s, the limit; raise --limit to see all")
    return found


def issue_relationships(issues: list[dict[str, Any]]) -> list[str]:
    """Enrich CLI issues via GraphQL; unavailable relationships must not hide the repo."""
    warnings = []
    by_id = {i["id"]: i for i in issues if i.get("id")}
    ids = list(by_id)
    for offset in range(0, len(ids), 50):
        query = "query { nodes(ids: " + json.dumps(ids[offset:offset + 50]) + """ ) {
          ... on Issue { id parent { number url }
            blockedBy(first: 100) { nodes { number url } pageInfo { hasNextPage } }
          }
        }}"""
        try:
            result = _gh(["api", "graphql", "-f", "query=" + query])
            if result.get("errors"):
                raise RuntimeError("GitHub could not return issue relationships")
            for node in result["data"]["nodes"]:
                if node and node["id"] in by_id:
                    by_id[node["id"]].update(parent=node.get("parent"), blockedBy=node.get("blockedBy"))
                    if (node.get("blockedBy") or {}).get("pageInfo", {}).get("hasNextPage"):
                        warnings.append("Some issue dependency links exceed the 100-link limit and are omitted.")
        except RuntimeError:
            warnings.append("Some issue relationship links are unavailable; PR and issue lists are still shown.")
    return list(dict.fromkeys(warnings))


def fetch(
    repo: str | None,
    days: int,
    limit: int,
    extra_prs: set[int],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Everything the page needs from GitHub, as one JSON-ready dict.

    Args:
        repo: "owner/name", or None for the repo in the current folder.
        days: How far back the Done tab goes.
        limit: Most pull requests or issues to fetch per list.
        extra_prs: Pull request numbers the plan points at; any not fetched already
            (closed long ago, say) are fetched one by one.
        now: The time to record; defaults to now. Tests pass a fixed time.
    """
    now = now or datetime.now(timezone.utc)
    flag = ["--repo", repo] if repo else []
    since = f"closed:>={(now - timedelta(days=days)).date().isoformat()}"
    info = _gh(["repo", "view", *([repo] if repo else []), "--json", "nameWithOwner,url"])
    data = {
        "repo": info["nameWithOwner"],
        "url": info["url"],
        "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "days": days,
        "open_prs": _listed("pr", "open", OPEN_PR_FIELDS, limit, flag),
        "closed_prs": _listed("pr", "closed", CLOSED_PR_FIELDS, limit, flag, since),
        "open_issues": _listed("issue", "open", OPEN_ISSUE_FIELDS, limit, flag),
        "closed_issues": _listed("issue", "closed", CLOSED_ISSUE_FIELDS, limit, flag, since),
        "releases": _gh(["release", "list", *flag, "--limit", "100", "--json", "tagName,publishedAt"]),
        "other_prs": [],
    }
    data["warnings"] = issue_relationships(data["open_issues"])
    known = {pr["number"] for pr in data["open_prs"] + data["closed_prs"]}
    for number in sorted(extra_prs - known):
        try:
            data["other_prs"].append(_gh(["pr", "view", str(number), *flag, "--json", ONE_PR_FIELDS]))
        except RuntimeError:
            logger.warning(f"the plan points at #{number}, which GitHub does not know")
    return data


def all_prs(data: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Every fetched pull request, by number."""
    return {pr["number"]: pr for pr in data["open_prs"] + data["closed_prs"] + data["other_prs"]}


def checks_state(pr: dict[str, Any]) -> str:
    """ "failing", "pending", "passing", or "none", from a PR's status checks."""
    results = []
    for check in pr.get("statusCheckRollup") or []:
        if check.get("__typename") == "StatusContext":
            results.append(check.get("state") or "PENDING")
        elif check.get("status") != "COMPLETED":
            results.append("PENDING")
        else:
            results.append(check.get("conclusion") or "PENDING")
    if not results:
        return "none"
    if any(r in FAILED for r in results):
        return "failing"
    if any(r in {"PENDING", "EXPECTED", "QUEUED", "IN_PROGRESS"} for r in results):
        return "pending"
    return "passing"


def pr_group(pr: dict[str, Any]) -> str:
    """Which PR_GROUPS key an open pull request belongs in. The first rule that fits wins."""
    if pr.get("isDraft"):
        return "draft"
    if checks_state(pr) == "failing":
        return "failing"
    if pr.get("reviewDecision") == "CHANGES_REQUESTED":
        return "author"
    if pr.get("reviewDecision") == "APPROVED":
        return "ready"
    return "review"


def closes(pr: dict[str, Any], repo: str) -> list[int]:
    """Numbers of the issues in this repo that a pull request says it closes."""
    numbers = []
    for ref in pr.get("closingIssuesReferences") or []:
        url = ref.get("url", "")
        if not url or f"/{repo}/issues/" in url:
            numbers.append(ref["number"])
    return numbers


def issue_prs(data: dict[str, Any]) -> dict[int, list[int]]:
    """For each issue number, the open pull requests that say they close it."""
    found: dict[int, list[int]] = {}
    for pr in data["open_prs"]:
        for number in closes(pr, data["repo"]):
            found.setdefault(number, []).append(pr["number"])
    return found


def issue_group(issue: dict[str, Any], prs_for_issue: dict[int, list[int]]) -> str:
    """Which ISSUE_GROUPS key an open issue belongs in."""
    if prs_for_issue.get(issue["number"]):
        return "pr"
    if issue.get("assignees"):
        return "assigned"
    return "nobody"


def grouped(items: list[dict[str, Any]], key_of: Any, order: dict[str, Any]) -> dict[str, list]:
    """Items sorted into groups, in the order of `order`, oldest first inside each group."""
    groups: dict[str, list] = {key: [] for key in order}
    for item in sorted(items, key=lambda i: i["createdAt"]):
        groups[key_of(item)].append(item)
    return groups


def _parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def age(stamp: str, now: str) -> str:
    """How long ago a GitHub time stamp was, in plain words: "today", "3 days", "5 weeks"."""
    days = (_parse(now) - _parse(stamp)).days
    if days < 1:
        return "today"
    if days < 14:
        return f"{days} day{'s' if days > 1 else ''}"
    if days < 70:
        return f"{days // 7} weeks"
    return f"{days // 30} months"


def done_groups(data: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Closed pull requests and issues, grouped by the release that shipped them, newest first.

    Each one sits under the first release published after it closed. Those closed after
    the last release sit under "Not released yet". A repo with no releases is grouped
    by the month things closed instead.
    """
    done = [{**pr, "kind": "pr"} for pr in data["closed_prs"]]
    done += [{**issue, "kind": "issue"} for issue in data["closed_issues"]]
    done.sort(key=lambda d: d["closedAt"], reverse=True)
    releases = sorted(
        (r for r in data["releases"] if r.get("publishedAt")), key=lambda r: r["publishedAt"]
    )
    groups: dict[str, list] = {}
    for item in done:
        if releases:
            after = [r for r in releases if r["publishedAt"] >= item["closedAt"]]
            name = after[0]["tagName"] if after else "Not released yet"
        else:
            name = _parse(item["closedAt"]).strftime("%B %Y")
        groups.setdefault(name, []).append(item)
    return list(groups.items())
