"""Watch several repos from one place: one page per repo, plus an overview page.

This is the manager's view. Nothing is added to the watched repos: a list of them
lives in one repo of your own, and that repo's daily Action builds the pages.

The watch list is a YAML file:

    repos:
      - sv642-hub/app-assignment-1                 # just the name
      - repo: example-org/pantry-planner            # or the name and its plan's path
        plan: docs/img/architecture.yaml

Each repo's plan is read from that repo on GitHub, at `plan` or else at
docs/plan.yaml. A repo without one simply gets no Plan tab.
"""

import re
from datetime import datetime, timezone
from typing import Any, Callable

import yaml

import dashboard_github as github
import dashboard_plan as plans

REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
DEFAULT_PLAN = "docs/plan.yaml"


class WatchListError(ValueError):
    """The watch list has a mistake. The message names what to fix."""


def load_watch_list(text: str, source: str = "watch list") -> list[dict[str, Any]]:
    """Parse a watch list into [{"repo": "owner/name", "plan": path or None}, ...].

    Raises:
        WatchListError: for a missing `repos` list, a badly written name, or a repeat.
    """
    try:
        found = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise WatchListError(f"{source}: not valid YAML: {error}") from error
    if not isinstance(found, dict) or not isinstance(found.get("repos"), list) or not found["repos"]:
        raise WatchListError(f"{source}: needs a `repos` list with at least one repo")
    entries = []
    for entry in found["repos"]:
        if isinstance(entry, str):
            entry = {"repo": entry}
        if not isinstance(entry, dict) or set(entry) - {"repo", "plan"}:
            raise WatchListError(f"{source}: each entry is a repo name, or has only repo and plan")
        name = entry.get("repo")
        if not isinstance(name, str) or not REPO_NAME.match(name):
            raise WatchListError(f"{source}: {name!r} is not written as owner/name")
        if any(e["repo"].lower() == name.lower() for e in entries):
            raise WatchListError(f"{source}: {name} is listed twice")
        plan = entry.get("plan")
        if plan is not None and not isinstance(plan, str):
            raise WatchListError(f"{source}: the plan for {name} must be a path")
        entries.append({"repo": name, "plan": plan})
    return entries


def page_name(repo: str) -> str:
    """The file a repo's page is saved as: "owner/name" becomes "owner__name.html".

    Safe as a file name, because load_watch_list only allows letters, digits, _ . and -.
    """
    return repo.replace("/", "__") + ".html"


def _newest(data: dict[str, Any]) -> str | None:
    """The time of the newest activity: a PR or issue opened, updated, or closed."""
    stamps = [
        thing.get(key)
        for kind in ("open_prs", "closed_prs", "open_issues", "closed_issues")
        for thing in data[kind]
        for key in ("updatedAt", "closedAt", "createdAt")
    ]
    stamps = [s for s in stamps if s]
    return max(stamps) if stamps else None


def summary(repo: str, data: dict[str, Any], plan: dict[str, Any] | None) -> dict[str, Any]:
    """The numbers the overview shows for one repo."""
    groups = github.grouped(data["open_prs"], github.pr_group, github.PR_GROUPS)
    prs_for_issue = github.issue_prs(data)
    row = {
        "repo": repo,
        "page": page_name(repo),
        "url": data["url"],
        "open_prs": len(data["open_prs"]),
        "ready": len(groups["ready"]),
        "review": len(groups["review"]),
        "failing": len(groups["failing"]),
        "open_issues": len(data["open_issues"]),
        "nobody": sum(github.issue_group(i, prs_for_issue) == "nobody" for i in data["open_issues"]),
        "newest": _newest(data),
        "fetched_at": data["fetched_at"],
        "plan": None,
        "error": None,
    }
    if plan:
        items = [item for _, _, box in plans.boxes(plan) for item in box["items"]]
        prs = github.all_prs(data)
        row["plan"] = {
            "built": sum(item["status"] == "built" for item in items),
            "items": len(items),
            "to_update": sum(plans.pr_check(item, prs) is not None for item in items),
        }
    return row


def watch(
    entries: list[dict[str, Any]],
    get_plan: Callable[[str, str], str | None],
    get_data: Callable[[str, set[int]], dict[str, Any]],
    render_page: Callable[[dict[str, Any], dict[str, Any] | None], str],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Build every watched repo's page, and its row on the overview.

    One repo failing (no access, a broken plan) does not stop the others: its row
    says what went wrong instead.

    Args:
        entries: From load_watch_list.
        get_plan: (repo, path) -> the plan file's text, or None if the repo has none.
        get_data: (repo, PR numbers the plan points at) -> GitHub's data for the repo.
        render_page: (data, plan) -> the repo's HTML page.

    Returns:
        The pages by file name, and one overview row per repo, in list order.
    """
    pages, rows = {}, []
    for entry in entries:
        repo = entry["repo"]
        try:
            path = entry["plan"] or DEFAULT_PLAN
            text = get_plan(repo, path)
            if text is None and entry["plan"]:
                raise plans.PlanError(f"{repo}: no file at {path}")
            plan = plans.load_plan(text, f"{repo}/{path}") if text is not None else None
            data = get_data(repo, plans.plan_prs(plan) if plan else set())
            pages[page_name(repo)] = render_page(data, plan)
            rows.append(summary(repo, data, plan))
        except (plans.PlanError, RuntimeError) as error:
            rows.append({"repo": repo, "url": f"https://github.com/{repo}", "error": str(error)})
    return pages, rows


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
