"""The HTML page: its tabs, what it flags, and that text from GitHub cannot run as code."""

import re

from conftest import issue, pr

import dashboard_page as page


def test_the_plan_tab_is_there_only_with_a_plan(demo_plan: dict, demo_data: dict) -> None:
    with_plan = page.render(demo_data, demo_plan)
    without = page.render(demo_data, None)
    assert 'data-tab="plan"' in with_plan
    assert 'data-tab="plan"' not in without
    for tab in ("prs", "issues", "graph", "done"):
        assert f'id="{tab}"' in with_plan and f'id="{tab}"' in without


def test_the_plan_tab_flags_prs_that_merged_or_closed(demo_plan: dict, demo_data: dict) -> None:
    html = page.render(demo_data, demo_plan)
    assert ">merged 2026-11-08<" in html  # #39, still marked pr on the plan
    assert ">closed, not merged<" in html  # #38
    assert "Open pull requests not on the plan (3)" in html  # #43, #46, #48


def test_box_owners_and_statuses_are_shown(demo_plan: dict, demo_data: dict) -> None:
    html = page.render(demo_data, demo_plan)
    assert "Owner: not assigned" in html  # Monitoring has owner: null
    assert 'data-search="monitoring not assigned not built"' in html  # so search finds it
    assert "Owner: Dee Ross" in html  # a box's own owner beats its group's
    assert "Partly built<br>1 of 3 in review" in html  # Pantry list


def test_pr_and_issue_tabs_count_each_group(demo_plan: dict, demo_data: dict) -> None:
    html = page.render(demo_data, demo_plan)
    for text in [
        "Ready to merge (1)",
        "Needs review (4)",
        "Waiting on the author (1)",
        "Checks failing (1)",
        "Draft (1)",
        "Nobody on it yet (5)",
        "A pull request is open (4)",
    ]:
        assert text in html
    assert "Someone is on it (" not in html  # an empty group gets no section


def test_text_from_github_is_escaped(data: dict) -> None:
    evil = '<script>alert("x")</script>'
    data["open_prs"].append(pr(11, "a", title=evil, statusCheckRollup=[]))
    data["open_issues"].append(issue(21, title=evil, labels=[{"name": evil}]))
    html = page.render(data, None)
    assert evil not in html
    assert "&lt;script&gt;" in html
    assert len(re.findall(r"<script>", html)) == 2  # only the page's own two scripts


def test_a_link_that_is_not_a_web_address_is_dropped(data: dict) -> None:
    data["open_prs"].append(pr(11, "a", url="javascript:alert(1)", statusCheckRollup=[]))
    html = page.render(data, None)
    assert "javascript:" not in html


def test_the_graph_says_what_it_left_out(demo_plan: dict, demo_data: dict) -> None:
    html = page.render(demo_data, demo_plan)
    assert html.count('class="cluster"') >= 3
    assert "Left out because nothing links to them: 2 open pull requests and 2 open issues" in html


def test_an_empty_repo_still_renders() -> None:
    empty = {
        "repo": "o/r",
        "url": "https://github.com/o/r",
        "fetched_at": "2026-11-12T08:00:00Z",
        "days": 90,
        "open_prs": [],
        "closed_prs": [],
        "open_issues": [],
        "closed_issues": [],
        "releases": [],
        "other_prs": [],
    }
    html = page.render(empty, None)
    assert "No open pull requests." in html
    assert "Nothing links up yet." in html
    assert "Nothing closed in this time." in html
