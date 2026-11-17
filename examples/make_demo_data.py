"""Write the demo data: examples/demo/ (Pantry Planner) and examples/demo-watch/ (three repos).

The people, pull requests, and issues are invented. The file has the same shape
`dashboard.py fetch` saves, so the demo page and the tests need no network:

    python examples/make_demo_data.py
    python skills/repo-radar/scripts/dashboard.py build \
        --data examples/demo/data.json --plan examples/demo/plan.yaml --out demo.html
"""

import json
from pathlib import Path
from typing import Any

REPO = "example-org/pantry-planner"
URL = f"https://github.com/{REPO}"
OUT = Path(__file__).resolve().parent / "demo" / "data.json"


def _checks(result: str) -> list[dict[str, Any]]:
    if result == "none":
        return []
    if result == "PENDING":
        return [{"__typename": "CheckRun", "name": "tests", "status": "IN_PROGRESS", "conclusion": ""}]
    return [{"__typename": "CheckRun", "name": "tests", "status": "COMPLETED", "conclusion": result}]


def open_pr(number, title, login, created, head, *, base="main", draft=False, review="",
            checks="SUCCESS", closes=(), size=(40, 10, 3), labels=()) -> dict[str, Any]:
    return {
        "number": number, "title": title, "state": "OPEN", "author": {"login": login},
        "url": f"{URL}/pull/{number}", "isDraft": draft, "createdAt": created,
        "updatedAt": created, "baseRefName": base, "headRefName": head,
        "headRepository": {"name": "pantry-planner"},
        "headRepositoryOwner": {"login": "example-org"},
        "reviewDecision": review, "statusCheckRollup": _checks(checks),
        "closingIssuesReferences": [
            {"number": n, "url": f"{URL}/issues/{n}"} for n in closes
        ],
        "additions": size[0], "deletions": size[1], "changedFiles": size[2],
        "labels": [{"name": name} for name in labels],
    }


def closed_pr(number, title, login, closed, merged=True) -> dict[str, Any]:
    return {
        "number": number, "title": title, "state": "MERGED" if merged else "CLOSED",
        "author": {"login": login}, "url": f"{URL}/pull/{number}", "createdAt": closed,
        "closedAt": closed, "mergedAt": closed if merged else None, "labels": [],
    }


def open_issue(number, title, login, created, *, assignees=(), parent=None, blocked_by=(),
               labels=()) -> dict[str, Any]:
    return {
        "number": number, "title": title, "state": "OPEN", "author": {"login": login},
        "url": f"{URL}/issues/{number}", "createdAt": created, "updatedAt": created,
        "labels": [{"name": name} for name in labels],
        "assignees": [{"login": a} for a in assignees],
        "parent": {"number": parent} if parent else None,
        "blockedBy": {"nodes": [{"number": n} for n in blocked_by], "totalCount": len(blocked_by)},
    }


def closed_issue(number, title, login, closed, reason="COMPLETED") -> dict[str, Any]:
    return {
        "number": number, "title": title, "state": "CLOSED", "stateReason": reason,
        "author": {"login": login}, "url": f"{URL}/issues/{number}", "createdAt": closed,
        "closedAt": closed, "labels": [],
    }


def pushed(sha: str, title: str, login: str, when: str) -> dict[str, Any]:
    """A commit pushed straight to main, with no pull request."""
    oid = (sha * 40)[:40]
    return {"oid": oid, "title": title, "url": f"{URL}/commit/{oid}", "committedAt": when,
            "author": {"login": login, "name": login}}


def demo() -> dict[str, Any]:
    return {
        "repo": REPO,
        "url": URL,
        "fetched_at": "2026-11-12T08:00:00Z",
        "source": "made-up example data",  # shown in the page header instead of "from GitHub"
        "days": 90,
        "open_prs": [
            open_pr(41, "Share a shopping list by link", "ana-lee", "2026-11-03T10:00:00Z",
                    "app/share-link", review="APPROVED", closes=[13], size=(220, 31, 7)),
            open_pr(42, "Sort list items by aisle", "ana-lee", "2026-11-06T09:00:00Z",
                    "app/sort-aisle", review="REVIEW_REQUIRED", closes=[14], size=(140, 12, 4)),
            open_pr(43, "Remember each store's aisle order", "ana-lee", "2026-11-10T15:00:00Z",
                    "app/aisle-memory", base="app/sort-aisle", draft=True, size=(90, 5, 3)),
            open_pr(44, "Queue edits made offline and send them later", "bokim",
                    "2026-10-28T12:00:00Z", "sync/offline-queue", review="CHANGES_REQUESTED",
                    closes=[16], size=(310, 44, 9)),
            open_pr(45, "Retry sync with backoff", "bokim", "2026-11-09T08:30:00Z",
                    "sync/retry", checks="FAILURE", size=(75, 20, 2)),
            open_pr(46, "Bump pytest from 9.0 to 9.1", "app/dependabot", "2026-11-11T04:00:00Z",
                    "dependabot/pip/pytest-9.1", size=(2, 2, 1), labels=["dependencies"]),
            open_pr(47, "Back up the database every night", "cypark", "2026-11-05T14:00:00Z",
                    "infra/nightly-backup", review="REVIEW_REQUIRED", checks="PENDING",
                    closes=[18], size=(120, 8, 5)),
            open_pr(48, "Docs: how to run the app locally", "dee-ross", "2026-11-11T16:00:00Z",
                    "docs/run-locally", size=(60, 3, 1), labels=["docs"]),
        ],
        "closed_prs": [
            closed_pr(39, "Scan barcodes with the phone camera", "ana-lee", "2026-11-08T11:00:00Z"),
            closed_pr(38, "Sync with a websocket instead of polling", "bokim",
                      "2026-11-04T17:00:00Z", merged=False),
            closed_pr(37, "Pantry list: add, edit, remove items", "ana-lee", "2026-10-25T10:00:00Z"),
            closed_pr(36, "Sign in with an email link", "dee-ross", "2026-10-20T09:00:00Z"),
            closed_pr(35, "Deploy to a small VM with one command", "cypark", "2026-10-14T13:00:00Z"),
            closed_pr(34, "Sync: push local changes to the server", "bokim", "2026-09-30T10:00:00Z"),
            closed_pr(33, "Database schema for lists and items", "cypark", "2026-09-20T10:00:00Z"),
        ],
        "open_issues": [
            open_issue(12, "Sharing lists with a household", "dee-ross", "2026-10-01T09:00:00Z",
                       labels=["epic"]),
            open_issue(13, "Share a list by link", "dee-ross", "2026-10-01T09:05:00Z",
                       assignees=["ana-lee"], parent=12, labels=["feature"]),
            open_issue(14, "Sort the list by aisle", "ana-lee", "2026-10-15T12:00:00Z",
                       assignees=["ana-lee"], labels=["feature"]),
            open_issue(15, "Barcode scanner crashes on old Android phones", "dee-ross",
                       "2026-11-09T19:00:00Z", labels=["bug"]),
            open_issue(16, "Edits made offline are lost", "bokim", "2026-10-20T08:00:00Z",
                       assignees=["bokim"], labels=["bug"]),
            open_issue(17, "Sync conflicts: the last write wins and loses data", "bokim",
                       "2026-10-22T08:00:00Z", blocked_by=[16], labels=["bug"]),
            open_issue(18, "Back up the database every night", "cypark", "2026-10-30T10:00:00Z",
                       assignees=["cypark"], labels=["infra"]),
            open_issue(19, "Dark mode for the app", "ana-lee", "2026-11-02T10:00:00Z",
                       labels=["feature"]),
            open_issue(20, "Suggest meals from what is in the pantry", "dee-ross",
                       "2026-11-11T21:00:00Z", parent=12, labels=["idea"]),
        ],
        "closed_issues": [
            closed_issue(8, "Camera permission prompt shows twice", "ana-lee", "2026-11-08T11:30:00Z"),
            closed_issue(7, "Use a websocket for sync", "bokim", "2026-11-04T17:05:00Z", "NOT_PLANNED"),
            closed_issue(6, "Items with emoji names break sorting", "dee-ross", "2026-10-26T10:00:00Z"),
            closed_issue(5, "Need a way to sign in", "dee-ross", "2026-10-20T09:30:00Z"),
        ],
        "releases": [
            {"tagName": "v0.2.0", "publishedAt": "2026-10-31T12:00:00Z"},
            {"tagName": "v0.1.0", "publishedAt": "2026-10-01T12:00:00Z"},
        ],
        "other_prs": [],
        "pushes": [
            pushed("a1f3", "Fix a typo in the README", "dee-ross", "2026-11-07T10:00:00Z"),
            pushed("b7c2", "Update the staging server address", "cypark", "2026-10-29T16:00:00Z"),
        ],
    }


def _as_repo(data: dict[str, Any], repo: str) -> dict[str, Any]:
    """The same kind of data, moved to another made-up repo (every link points there)."""
    text = json.dumps(data).replace(URL, f"https://github.com/{repo}")
    text = text.replace('"name": "pantry-planner"', f'"name": "{repo.split("/")[1]}"')
    return {**json.loads(text), "repo": repo, "url": f"https://github.com/{repo}"}


def recipe_api() -> dict[str, Any]:
    """A busy repo with no plan: several PRs waiting, one ready, issues nobody has picked up."""
    data = {
        **demo(),
        "open_prs": [
            open_pr(61, "Search recipes by what is in the pantry", "cypark", "2026-11-10T09:00:00Z",
                    "search/by-pantry", review="APPROVED", closes=[52], size=(260, 40, 8)),
            open_pr(62, "Cache recipe lookups for an hour", "bokim", "2026-11-07T11:00:00Z",
                    "perf/cache", review="REVIEW_REQUIRED", size=(90, 12, 3)),
            open_pr(63, "Return nutrition facts with each recipe", "dee-ross", "2026-11-12T07:00:00Z",
                    "api/nutrition", size=(150, 6, 5)),
        ],
        "open_issues": [
            open_issue(52, "Find recipes from the ingredients I have", "ana-lee", "2026-10-28T10:00:00Z",
                       assignees=["cypark"], labels=["feature"]),
            open_issue(53, "Recipe images load slowly", "dee-ross", "2026-11-05T10:00:00Z", labels=["bug"]),
            open_issue(54, "Rate limit the public endpoints", "bokim", "2026-11-09T10:00:00Z",
                       labels=["security"]),
            open_issue(55, "Units: grams or cups", "ana-lee", "2026-11-11T10:00:00Z", labels=["question"]),
        ],
        "closed_prs": [
            closed_pr(60, "First version of the recipe endpoints", "cypark", "2026-11-03T10:00:00Z"),
            closed_pr(59, "Database for recipes and ingredients", "bokim", "2026-10-21T10:00:00Z"),
        ],
        "closed_issues": [closed_issue(51, "Pick a recipe data source", "ana-lee", "2026-10-15T10:00:00Z")],
        "releases": [],
        "pushes": [],
    }
    return _as_repo(data, "example-org/recipe-api")


def mobile_app() -> dict[str, Any]:
    """A repo where people push straight to main: one old PR with a failing check, no merged PRs."""
    data = {
        **demo(),
        "open_prs": [
            open_pr(14, "Upgrade the app framework", "dee-ross", "2026-09-04T10:00:00Z",
                    "chore/upgrade", checks="FAILURE", size=(800, 640, 41)),
        ],
        "open_issues": [
            open_issue(11, "App icon looks blurry on tablets", "ana-lee", "2026-09-02T10:00:00Z",
                       labels=["bug"]),
            open_issue(12, "Push notifications when a list is shared", "bokim", "2026-09-10T10:00:00Z",
                       assignees=["dee-ross"], labels=["feature"]),
        ],
        "closed_prs": [],
        "closed_issues": [],
        "releases": [],
        "pushes": [
            pushed("c4d9", "Fix the crash when the list is empty", "dee-ross", "2026-11-10T19:00:00Z"),
            pushed("d2e8", "Add the share button to the list screen", "bokim", "2026-11-04T12:00:00Z"),
            pushed("e5a1", "Bump the app version to 1.3", "dee-ross", "2026-10-21T09:00:00Z"),
        ],
    }
    return _as_repo(data, "example-org/mobile-app")


WATCH_DIR = Path(__file__).resolve().parent / "demo-watch"

# What the skill writes when someone asks it to summarize the commits (see SKILL.md).
MOBILE_SUMMARIES = {
    "c4d9": "Shows an empty-list message instead of crashing when a list has no items",
    "d2e8": "Adds a Share button to the list screen that opens the phone's share sheet",
    "e5a1": "Raises the app version to 1.3 for the next store release",
}


def mobile_summaries() -> str:
    """The mobile-app repo's .github/dashboard/summaries.yaml."""
    lines = [
        "# What each commit or merged pull request changed, written by AI from its changes.",
        "# The page shows these marked as AI summaries, with the original message under them.",
        "# Add to it with `dashboard.py summarize --add`; fix a wrong line by hand.",
        "commits:",
    ]
    lines += [f"  '{(sha * 40)[:40]}': {json.dumps(text)}" for sha, text in MOBILE_SUMMARIES.items()]
    lines += [
        "prs: {}",
        "digest:",
        "  written: '2026-11-12'",
        "  covers: the last 3 commits, up to c4d9c4d",
        "  groups:",
        "  - title: Sharing",
        "    items:",
        "    - A Share button on the list screen opens the phone's share sheet",
        "  - title: Fixes and release",
        "    items:",
        "    - The app no longer crashes when a list is empty; it shows a message instead",
        "    - The version is now 1.3, ready for the next store release",
    ]
    return "\n".join([*lines, ""])


def watch_files() -> dict[str, str]:
    """The saved data `dashboard.py watch --data-dir examples/demo-watch` reads, by file name."""
    plan = (OUT.parent / "plan.yaml").read_text(encoding="utf-8")
    return {
        "example-org__pantry-planner.json": json.dumps(demo(), indent=1) + "\n",
        "example-org__pantry-planner.plan.yaml": plan,
        "example-org__recipe-api.json": json.dumps(recipe_api(), indent=1) + "\n",
        "example-org__mobile-app.json": json.dumps(mobile_app(), indent=1) + "\n",
        "example-org__mobile-app.summaries.yaml": mobile_summaries(),
    }


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(demo(), indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    WATCH_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in watch_files().items():
        (WATCH_DIR / name).write_text(text, encoding="utf-8")
        print(f"wrote {WATCH_DIR / name}")
