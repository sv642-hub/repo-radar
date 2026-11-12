"""Shared test data: a small made-up plan, its pull requests, and the demo project."""

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "repo-radar" / "scripts"
DEMO = ROOT / "examples" / "demo"
sys.path.insert(0, str(SCRIPTS))


def pr(number: int, login: str, state: str = "OPEN", **extra: Any) -> dict[str, Any]:
    """A pull request as gh returns it, with only the fields the code reads."""
    return {
        "number": number,
        "title": f"PR {number}",
        "state": state,
        "author": {"login": login},
        "url": f"https://github.com/o/r/pull/{number}",
        "headRefName": f"branch-{number}",
        "baseRefName": "main",
        "isDraft": False,
        "createdAt": "2026-11-01T12:00:00Z",
        "mergedAt": "2026-11-10T12:00:00Z" if state == "MERGED" else None,
        "closedAt": None if state == "OPEN" else "2026-11-10T12:00:00Z",
        **extra,
    }


def issue(number: int, login: str = "ana", **extra: Any) -> dict[str, Any]:
    return {
        "number": number,
        "title": f"Issue {number}",
        "state": "OPEN",
        "author": {"login": login},
        "url": f"https://github.com/o/r/issues/{number}",
        "createdAt": "2026-11-01T12:00:00Z",
        "labels": [],
        "assignees": [],
        **extra,
    }


PLAN: dict[str, Any] = {
    "title": "Test plan",
    "as_of": "main at abc1234, checked 2026-11-12",
    "people": {"Ana Lee": "ana", "Bo Kim": "bo"},
    "groups": {
        "mine": {
            "title": "Mine",
            "owner": "Ana Lee",
            "boxes": [
                {
                    "title": "Box A",
                    "items": [
                        {"status": "built", "text": "done"},
                        {"status": "pr", "pr": 1, "text": "open work"},
                        {"status": "pr", "pr": 2, "text": "merged work"},
                        {"status": "pr", "pr": 3, "text": "closed work"},
                        {"status": "missing", "text": "todo"},
                    ],
                },
                {
                    "title": "Box lent out",
                    "owner": "Bo Kim",
                    "items": [{"status": "missing", "text": "Bo's item in Ana's group"}],
                },
            ],
        },
        "theirs": {
            "title": "Theirs",
            "owner": "Bo Kim",
            "boxes": [
                {"title": "Box B", "items": [{"status": "pr", "pr": 9, "text": "Bo's PR"}]},
                {
                    "title": "Box borrowed",
                    "owner": "Ana Lee",
                    "items": [{"status": "missing", "text": "Ana's item in Bo's group"}],
                },
            ],
        },
        "shared": {
            "title": "Shared",
            "owner": "Everyone",
            "boxes": [
                {
                    "title": "Box C",
                    "items": [
                        {"status": "pr", "pr": 4, "text": "Ana's PR in a shared box"},
                        {"status": "missing", "text": "nobody's yet", "issue": 20},
                    ],
                }
            ],
        },
    },
}

PRS = [
    pr(1, "ana"),
    pr(2, "ana", "MERGED"),
    pr(3, "ana", "CLOSED"),
    pr(4, "ana"),
    pr(5, "ana"),
    pr(6, "ana", "MERGED"),
    pr(9, "bo"),
    pr(10, "bo"),
]
ANA_PRS = {1, 2, 3, 4, 5, 6}


@pytest.fixture
def plan() -> dict[str, Any]:
    return copy.deepcopy(PLAN)


@pytest.fixture
def data() -> dict[str, Any]:
    """GitHub data matching PLAN."""
    return {
        "repo": "o/r",
        "url": "https://github.com/o/r",
        "fetched_at": "2026-11-12T08:00:00Z",
        "days": 90,
        "open_prs": [p for p in copy.deepcopy(PRS) if p["state"] == "OPEN"],
        "closed_prs": [p for p in copy.deepcopy(PRS) if p["state"] != "OPEN"],
        "open_issues": [issue(20)],
        "closed_issues": [],
        "releases": [],
        "other_prs": [],
    }


@pytest.fixture
def demo_data() -> dict[str, Any]:
    return json.loads((DEMO / "data.json").read_text(encoding="utf-8"))


@pytest.fixture
def demo_plan() -> dict[str, Any]:
    import dashboard_plan

    return dashboard_plan.load_plan((DEMO / "plan.yaml").read_text(encoding="utf-8"))
