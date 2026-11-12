"""Sorting what GitHub says: PR groups, issue groups, ages, and releases."""

from typing import Any

import pytest
from conftest import issue, pr

import dashboard_github as github


def _check(conclusion: str, status: str = "COMPLETED") -> dict[str, Any]:
    return {"__typename": "CheckRun", "status": status, "conclusion": conclusion}


@pytest.mark.parametrize(
    "rollup, expected",
    [
        ([], "none"),
        (None, "none"),
        ([_check("SUCCESS"), _check("SKIPPED")], "passing"),
        ([_check("SUCCESS"), _check("FAILURE")], "failing"),
        ([_check("", "IN_PROGRESS")], "pending"),
        ([{"__typename": "StatusContext", "state": "ERROR"}], "failing"),
        ([{"__typename": "StatusContext", "state": "PENDING"}, _check("SUCCESS")], "pending"),
    ],
)
def test_checks_state(rollup: Any, expected: str) -> None:
    assert github.checks_state({"statusCheckRollup": rollup}) == expected


def test_pr_groups_follow_the_rules_in_order() -> None:
    failing = [_check("FAILURE")]
    assert github.pr_group(pr(1, "a", isDraft=True, statusCheckRollup=failing)) == "draft"
    assert github.pr_group(pr(1, "a", statusCheckRollup=failing, reviewDecision="APPROVED")) == "failing"
    assert github.pr_group(pr(1, "a", reviewDecision="CHANGES_REQUESTED")) == "author"
    assert github.pr_group(pr(1, "a", reviewDecision="APPROVED")) == "ready"
    assert github.pr_group(pr(1, "a", reviewDecision="REVIEW_REQUIRED")) == "review"
    assert github.pr_group(pr(1, "a", reviewDecision="")) == "review"


def test_closes_keeps_only_issues_in_this_repo() -> None:
    refs = [
        {"number": 7, "url": "https://github.com/o/r/issues/7"},
        {"number": 8, "url": "https://github.com/other/repo/issues/8"},
        {"number": 9},
    ]
    assert github.closes(pr(1, "a", closingIssuesReferences=refs), "o/r") == [7, 9]


def test_issue_groups(data: dict) -> None:
    data["open_prs"].append(pr(11, "a", closingIssuesReferences=[{"number": 21}]))
    prs_for_issue = github.issue_prs(data)
    assert prs_for_issue == {21: [11]}
    assert github.issue_group(issue(21, assignees=[{"login": "a"}]), prs_for_issue) == "pr"
    assert github.issue_group(issue(22, assignees=[{"login": "a"}]), prs_for_issue) == "assigned"
    assert github.issue_group(issue(23), prs_for_issue) == "nobody"


def test_grouped_keeps_every_group_and_puts_the_oldest_first() -> None:
    items = [
        pr(1, "a", createdAt="2026-11-05T00:00:00Z"),
        pr(2, "a", createdAt="2026-11-01T00:00:00Z", isDraft=True),
        pr(3, "a", createdAt="2026-11-02T00:00:00Z"),
    ]
    groups = github.grouped(items, github.pr_group, github.PR_GROUPS)
    assert list(groups) == list(github.PR_GROUPS)
    assert [p["number"] for p in groups["review"]] == [3, 1]
    assert [p["number"] for p in groups["draft"]] == [2]


@pytest.mark.parametrize(
    "stamp, expected",
    [
        ("2026-11-12T07:00:00Z", "today"),
        ("2026-11-11T07:00:00Z", "1 day"),
        ("2026-11-02T08:00:00Z", "10 days"),
        ("2026-10-15T08:00:00Z", "4 weeks"),
        ("2026-06-12T08:00:00Z", "5 months"),
    ],
)
def test_age_in_plain_words(stamp: str, expected: str) -> None:
    assert github.age(stamp, "2026-11-12T08:00:00Z") == expected


def test_done_items_sit_under_the_first_release_after_they_closed(demo_data: dict) -> None:
    groups = dict(github.done_groups(demo_data))
    assert list(groups) == ["Not released yet", "v0.2.0", "v0.1.0"]
    assert {i["number"] for i in groups["Not released yet"]} == {39, 38, 8, 7}
    assert {i["number"] for i in groups["v0.1.0"]} == {34, 33}


def test_without_releases_done_items_are_grouped_by_month(demo_data: dict) -> None:
    demo_data["releases"] = []
    assert [name for name, _ in github.done_groups(demo_data)] == [
        "November 2026",
        "October 2026",
        "September 2026",
    ]


def test_all_prs_includes_prs_fetched_one_by_one(data: dict) -> None:
    data["other_prs"] = [pr(99, "a", "MERGED")]
    assert 99 in github.all_prs(data)
