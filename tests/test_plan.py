"""The plan file: its checks, box status, and one person's items against their PRs.

Most of the owner and PR tests come from Verness Chin's diagram-status skill.
"""

import copy
from typing import Any

import pytest
from conftest import ANA_PRS, PRS, pr

import dashboard_plan as plans


def _items(*statuses: str) -> list[dict[str, Any]]:
    return [{"status": s, "text": "x", **({"pr": 1} if s == "pr" else {})} for s in statuses]


# ---- checks


def test_the_test_plan_and_the_starter_template_pass_the_checks(plan: dict) -> None:
    from conftest import ROOT

    plans.check_plan(plan)
    template = ROOT / "skills" / "repo-dashboard" / "templates" / "plan.yaml"
    plans.load_plan(template.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda p: p.pop("title"), "title"),
        (lambda p: p.update(groups={}), "groups"),
        (lambda p: p["groups"]["mine"]["boxes"][0]["items"].append({"status": "done", "text": "x"}), "status must be"),
        (lambda p: p["groups"]["mine"]["boxes"][0]["items"].append({"status": "pr", "text": "x"}), "pr number"),
        (lambda p: p["groups"]["mine"]["boxes"][0]["items"].append({"status": "built", "text": "x", "pr": 4}), "pr number"),
        (lambda p: p["groups"]["mine"]["boxes"][0]["items"].append({"status": "built", "text": ""}), "needs text"),
        (lambda p: p["groups"]["mine"]["boxes"][0]["items"].append({"status": "built", "text": "x", "who": 1}), "only status"),
        (lambda p: p["groups"]["mine"]["boxes"][0]["items"].append({"status": "built", "text": "x", "issue": "7"}), "issue must"),
        (lambda p: p["groups"]["mine"].pop("owner"), "give an owner"),
        (lambda p: p["groups"]["mine"]["boxes"][0].update(items=[]), "at least one item"),
        (lambda p: p.update(people={"Ana": 5}), "people"),
    ],
)
def test_a_mistake_is_refused_with_a_message_naming_it(plan: dict, change: Any, message: str) -> None:
    change(plan)
    with pytest.raises(plans.PlanError, match=message):
        plans.check_plan(plan)


def test_a_null_owner_is_allowed_and_means_not_assigned(plan: dict) -> None:
    plan["groups"]["mine"]["owner"] = None
    plans.check_plan(plan)
    group = plan["groups"]["mine"]
    assert plans.box_owner(group, group["boxes"][0]) is None


def test_keys_from_an_older_diagram_file_are_allowed(plan: dict) -> None:
    plan["rows"] = [["mine", "theirs"]]
    plan["flow"] = {"label": "x"}
    plan["groups"]["mine"]["columns"] = 2
    plans.check_plan(plan)


def test_bad_yaml_is_refused_with_its_file_name() -> None:
    with pytest.raises(plans.PlanError, match="plan.yaml: not valid YAML"):
        plans.load_plan("title: [unclosed", "plan.yaml")


# ---- box status (from the original diagram renderer)


def test_a_box_is_in_review_only_when_everything_not_built_is_in_a_pr() -> None:
    assert plans.box_status(_items("built")) == "Built"
    assert plans.box_status(_items("pr")) == "In review"
    assert plans.box_status(_items("built", "pr")) == "In review"
    assert plans.box_status(_items("pr", "missing")) == "Not built"
    assert plans.box_status(_items("built", "pr", "missing")) == "Partly built"
    assert plans.box_status(_items("simulated", "pr")) == "Partly built"


def test_a_box_that_hides_its_reviews_says_how_many_there_are() -> None:
    assert plans.in_review_note(_items("pr", "missing", "missing")) == "1 of 3 in review"
    assert plans.in_review_note(_items("built", "pr", "missing")) == "1 of 3 in review"
    assert plans.in_review_note(_items("built", "pr")) is None
    assert plans.in_review_note(_items("missing")) is None


# ---- one person's items (from diagram-status)


def test_owned_items_follow_the_box_owner_not_only_the_group_owner(plan: dict) -> None:
    texts = {row["text"] for row in plans.owned_items(plan, "Ana Lee", ANA_PRS)}
    assert "Ana's item in Bo's group" in texts
    assert "Bo's item in Ana's group" not in texts
    assert "Bo's PR" not in texts


def test_an_item_pointing_at_my_pr_is_listed_even_in_a_shared_box(plan: dict) -> None:
    rows = plans.owned_items(plan, "Ana Lee", ANA_PRS)
    shared = [row for row in rows if row["group"] == "Shared"]
    assert [row["text"] for row in shared] == ["Ana's PR in a shared box"]
    assert shared[0]["listed_because"] == "your pull request"


def test_owner_names_match_ignoring_case_but_not_partial_names(plan: dict) -> None:
    assert plans.owned_items(plan, "  ana lee ", set())
    assert not plans.owned_items(plan, "Ana", set())


def test_each_pr_state_gets_its_own_action(plan: dict) -> None:
    rows = plans.owned_items(plan, "Ana Lee", ANA_PRS)
    findings = {f["pr"]: f for f in plans.check_items(rows, {p["number"]: p for p in PRS})}
    assert findings[1]["pr_state"] == "open"
    assert findings[2]["pr_state"] == "merged 2026-11-10"
    assert "built" in findings[2]["action"]
    assert findings[3]["pr_state"] == "closed, not merged"
    assert "missing" in findings[3]["action"]
    assert set(findings) == {1, 2, 3, 4}


def test_a_pr_number_github_does_not_know_is_flagged() -> None:
    rows = [{"status": "pr", "pr": 999, "text": "typo"}]
    assert plans.check_items(rows, {})[0]["pr_state"] == "not found"


def test_items_not_marked_pr_are_not_checked() -> None:
    rows = [{"status": "missing", "pr": None, "text": "todo"}]
    assert plans.check_items(rows, {}) == []


def test_unplaced_lists_only_open_prs_that_no_item_points_at(plan: dict) -> None:
    open_prs = [p for p in PRS if p["state"] == "OPEN"]
    assert [p["number"] for p in plans.unplaced_prs(plan, open_prs, "ana")] == [5]
    assert [p["number"] for p in plans.unplaced_prs(plan, open_prs)] == [5, 10]
    assert plans.unplaced_prs(plan, open_prs, "nobody") == []


def test_the_people_list_turns_a_login_into_an_owner_name(plan: dict) -> None:
    assert plans.owner_for_login(plan, "ANA") == "Ana Lee"
    assert plans.owner_for_login(plan, "cy") is None


def test_report_counts_every_listed_item_once(plan: dict) -> None:
    rows = plans.owned_items(plan, "Ana Lee", ANA_PRS)
    findings = plans.check_items(rows, {p["number"]: p for p in PRS})
    text = plans.report(plan, "Ana Lee", "ana", rows, findings, [pr(5, "ana")])
    assert "7 items (1 built, 0 simulated, 4 pr, 2 missing)" in text
    assert "| #5 | PR 5 |" in text


def test_nothing_here_changes_the_plan(plan: dict) -> None:
    before = copy.deepcopy(plan)
    rows = plans.owned_items(plan, "Ana Lee", ANA_PRS)
    plans.check_items(rows, {p["number"]: p for p in PRS})
    plans.unplaced_prs(plan, PRS)
    assert plan == before
