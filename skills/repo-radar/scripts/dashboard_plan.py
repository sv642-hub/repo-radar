"""The plan: a YAML file that lists every part of a system and how far each part is.

The plan is optional. Without it the dashboard shows only what GitHub knows. With
it, the dashboard also shows the parts nobody has opened a pull request for yet.

A plan has groups of boxes, and each box has items:

    title: "Pantry Planner: what is built"
    as_of: "checked against main on 2026-11-12"   # optional, written by the weekly refresh
    people:                                        # optional: owner name -> GitHub login
      Ana Lee: ana-lee
    groups:
      app:                                         # a short key, used only inside the file
        title: App
        subtitle: "src/app/"                       # optional
        owner: Ana Lee                             # every box in the group, unless a box says otherwise
        boxes:
          - title: Shopping list
            owner: Bo Kim                          # optional; null means nobody owns it yet
            items:
              - {status: built, text: "Add and remove items"}
              - {status: pr, pr: 12, text: "Share a list by link"}
              - {status: missing, text: "Sort by aisle", issue: 7}

Each item has a status:

    built      merged on main and working
    simulated  merged on main, but a stub, a fake, or a skeleton
    pr         in an open pull request; give its number as `pr`
    missing    not built yet

An item may also name the GitHub issue it comes from, as `issue`.

The functions that compare one person's items with their pull requests come from
Verness Chin's diagram-status skill.
"""

from typing import Any

import yaml

STATUSES = ("built", "simulated", "pr", "missing")
ITEM_KEYS = {"status", "text", "pr", "issue"}


class PlanError(ValueError):
    """The plan file has a mistake. The message names what to fix."""


def _fail(source: str, message: str) -> None:
    raise PlanError(f"{source}: {message}")


def _check_item(source: str, where: str, item: Any) -> None:
    """Refuse an item the dashboard would show wrongly."""
    if not isinstance(item, dict) or set(item) - ITEM_KEYS:
        _fail(source, f"{where}: an item has only status, text, pr, and issue")
    if item.get("status") not in STATUSES:
        _fail(source, f"{where}: status must be one of {list(STATUSES)}, got {item.get('status')!r}")
    if not isinstance(item.get("text"), str) or not item["text"].strip():
        _fail(source, f"{where}: an item needs text")
    if (item["status"] == "pr") != (type(item.get("pr")) is int):
        _fail(source, f"{where}: give a pr number exactly when the status is pr")
    if "issue" in item and type(item["issue"]) is not int:
        _fail(source, f"{where}: issue must be a number")


def check_plan(plan: Any, source: str = "plan") -> None:
    """Refuse a plan with a missing title, an empty group, a bad status, or a box with no owner.

    Keys the dashboard does not use (such as an older diagram file's `rows` and `flow`) are allowed,
    so an older diagram file works as a plan.

    Raises:
        PlanError: naming the first mistake found.
    """
    if not isinstance(plan, dict):
        _fail(source, "the file must be a mapping with title and groups")
    if not isinstance(plan.get("title"), str):
        _fail(source, "missing top-level key 'title'")
    if not isinstance(plan.get("groups"), dict) or not plan["groups"]:
        _fail(source, "missing top-level key 'groups', or it is empty")
    people = plan.get("people", {})
    if not isinstance(people, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in people.items()
    ):
        _fail(source, "people must map each owner name to a GitHub login")
    for key, group in plan["groups"].items():
        if not isinstance(group, dict) or not isinstance(group.get("title"), str):
            _fail(source, f"group {key} needs a title")
        if not isinstance(group.get("boxes"), list) or not group["boxes"]:
            _fail(source, f"group {key} has no boxes")
        for box in group["boxes"]:
            where = f"{key} / {box.get('title') if isinstance(box, dict) else box}"
            if not isinstance(box, dict) or not isinstance(box.get("title"), str):
                _fail(source, f"{where}: a box needs a title")
            if not isinstance(box.get("items"), list) or not box["items"]:
                _fail(source, f"{where}: a box needs at least one item")
            if "owner" not in box and "owner" not in group:
                _fail(source, f"{where}: give an owner (null if nobody owns it yet)")
            for item in box["items"]:
                _check_item(source, where, item)


def load_plan(text: str, source: str = "plan") -> dict[str, Any]:
    """Parse and check a plan file's text."""
    try:
        plan = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise PlanError(f"{source}: not valid YAML: {error}") from error
    check_plan(plan, source)
    return plan


def box_owner(group: dict[str, Any], box: dict[str, Any]) -> str | None:
    """A box's owner: its own, else its group's. None means nobody owns it yet."""
    return box["owner"] if "owner" in box else group.get("owner")


def same_name(a: str | None, b: str) -> bool:
    """Owner names match ignoring case and outer spaces."""
    return a is not None and a.strip().lower() == b.strip().lower()


def boxes(plan: dict[str, Any]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Every box in the plan, in file order, as (group key, group, box)."""
    return [(key, group, box) for key, group in plan["groups"].items() for box in group["boxes"]]


def box_status(items: list[dict[str, Any]]) -> str:
    """A box's status, from its items.

    "In review" only when every item not built on main is in a pull request, so a
    box with work still missing never reads as nearly done. A box with nothing on
    main is "Not built", even if some of it is in review; in_review_note says how much.
    """
    statuses = {item["status"] for item in items}
    if statuses == {"built"}:
        return "Built"
    if "pr" in statuses and statuses <= {"built", "pr"}:
        return "In review"
    if statuses <= {"pr", "missing"}:
        return "Not built"
    return "Partly built"


def in_review_note(items: list[dict[str, Any]]) -> str | None:
    """ "1 of 3 in review" for a box whose status hides the items in review, else None."""
    in_review = sum(item["status"] == "pr" for item in items)
    if not in_review or box_status(items) == "In review":
        return None
    return f"{in_review} of {len(items)} in review"


def plan_prs(plan: dict[str, Any]) -> set[int]:
    """Every pull request number any item points at."""
    return {item["pr"] for _, _, box in boxes(plan) for item in box["items"] if "pr" in item}


def pr_check(item: dict[str, Any], prs: dict[int, dict[str, Any]]) -> tuple[str, str] | None:
    """For an item marked pr: what GitHub says about that pull request, and what to do.

    Returns None for an item not marked pr, or whose pull request is still open.
    """
    if item["status"] != "pr":
        return None
    pr = prs.get(item["pr"])
    if pr is None:
        return "not found", "check the number; no such pull request in this repo"
    if pr["state"] == "OPEN":
        return None
    if pr["state"] == "MERGED":
        return f"merged {pr['mergedAt'][:10]}", "ready to mark built at the weekly refresh"
    return "closed, not merged", "set back to missing, or point at the PR that replaced it"


def owned_items(
    plan: dict[str, Any],
    owner: str,
    my_prs: set[int],
) -> list[dict[str, Any]]:
    """Every item in a box the person owns, plus any item that points at their PR.

    Args:
        plan: The parsed plan.
        owner: The person's name as the plan writes it.
        my_prs: Numbers of the pull requests the person opened.

    Returns:
        One row per item: group, box, owner, status, pr, text, and why it is listed.
    """
    rows = []
    for _, group, box in boxes(plan):
        owner_of_box = box_owner(group, box)
        mine = same_name(owner_of_box, owner)
        for item in box["items"]:
            if not mine and item.get("pr") not in my_prs:
                continue
            rows.append(
                {
                    "group": group["title"],
                    "box": box["title"],
                    "owner": owner_of_box,
                    "status": item["status"],
                    "pr": item.get("pr"),
                    "text": item["text"],
                    "listed_because": "your box" if mine else "your pull request",
                }
            )
    return rows


def check_items(
    rows: list[dict[str, Any]],
    prs: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Say, for each item marked pr, what GitHub says about that pull request.

    Args:
        rows: Items from owned_items.
        prs: Pull requests by number.

    Returns:
        One finding per item marked pr: the item, the PR's state, and what to do.
    """
    findings = []
    for row in rows:
        if row["status"] != "pr":
            continue
        result = pr_check(row, prs)
        state, action = result if result else ("open", "nothing to do")
        findings.append({**row, "pr_state": state, "action": action})
    return findings


def unplaced_prs(
    plan: dict[str, Any],
    open_prs: list[dict[str, Any]],
    login: str | None = None,
) -> list[dict[str, Any]]:
    """Open pull requests that no item in the plan points at; only `login`'s when given.

    Merged ones are left out: the weekly refresh places those, and old merged PRs
    from before the plan existed would bury the open ones.
    """
    placed = plan_prs(plan)
    return [
        pr
        for pr in open_prs
        if pr["number"] not in placed and (login is None or pr["author"]["login"] == login)
    ]


def owner_for_login(plan: dict[str, Any], login: str) -> str | None:
    """The owner name the plan's `people` list gives a GitHub login, if any."""
    for name, person_login in plan.get("people", {}).items():
        if person_login.lower() == login.lower():
            return name
    return None


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    """A Markdown table, or a line saying there is nothing to show."""
    if not rows:
        return "(none)\n"
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows:
        cells = [str(cell).replace("|", "/") if cell is not None else "" for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _box_rows(rows: list[dict[str, Any]]) -> list[list[Any]]:
    """One row per box: how many of the person's items are in each status."""
    counts: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        box = counts.setdefault((row["group"], row["box"]), {**{s: 0 for s in STATUSES}, "prs": []})
        box[row["status"]] += 1
        if row["pr"]:
            box["prs"].append(f"#{row['pr']}")
    return [
        [group, box, *(c[s] for s in STATUSES), ", ".join(c["prs"])]
        for (group, box), c in counts.items()
    ]


def report(
    plan: dict[str, Any],
    owner: str,
    login: str,
    rows: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    unplaced: list[dict[str, Any]],
) -> str:
    """The Markdown report for one person: their boxes, what is missing, and their PRs."""
    counts = {status: sum(r["status"] == status for r in rows) for status in STATUSES}
    summary = ", ".join(f"{n} {status}" for status, n in counts.items())
    as_of = " ".join(str(plan.get("as_of", "not set")).split())
    return "".join(
        [
            f"# Plan status for {owner} (@{login})\n\n",
            f"Plan as_of: {as_of}\n\n",
            f"## Your boxes: {len(rows)} items ({summary})\n\n",
            _table(["Group", "Box", *STATUSES, "PRs"], _box_rows(rows)),
            "\n## Items still missing\n\n",
            _table(
                ["Group", "Box", "Item"],
                [[r["group"], r["box"], r["text"]] for r in rows if r["status"] == "missing"],
            ),
            "\n## Items marked pr, checked against GitHub\n\n",
            _table(
                ["PR", "Item", "GitHub says", "What to do"],
                [[f"#{f['pr']}", f["text"], f["pr_state"], f["action"]] for f in findings],
            ),
            "\n## Your open pull requests with no item on the plan\n\n",
            _table(
                ["PR", "Title", "Branch", "Draft"],
                [[f"#{p['number']}", p["title"], p["headRefName"], p["isDraft"]] for p in unplaced],
            ),
        ]
    )
