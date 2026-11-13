"""How the open work relates: plan boxes, open issues, and open pull requests, as a graph.

Only links that GitHub or the plan already records are drawn:

    plan     a plan item points at an issue or a pull request
    closes   a pull request says it closes an issue
    sub      an issue is a sub-issue of another
    blocks   an issue is blocked by another
    stacked  a pull request is built on another pull request's branch

Closed work is left out, so the graph stays small enough to read. Things that link
to each other form a cluster, and each cluster is laid out on its own, in three
columns: plan boxes, then issues, then pull requests. Clusters never share a line,
so lines from one cluster never cross another.
"""

from typing import Any

from dashboard_github import closes
from dashboard_plan import boxes

COLUMNS = {"box": 0, "issue": 1, "pr": 2}
NODE_W = 290
NODE_H = 48
COL_GAP = 90
ROW_GAP = 12
CLUSTER_GAP = 30
MARGIN = 50  # room on both sides for the arcs between nodes in the same column


def box_key(group_key: str, box: dict[str, Any]) -> str:
    return f"box:{group_key}/{box['title']}"


def edges(plan: dict[str, Any] | None, data: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Every link between open things, as (from key, to key, kind). Keys are like "pr:12"."""
    open_prs = {pr["number"]: pr for pr in data["open_prs"]}
    open_issues = {issue["number"] for issue in data["open_issues"]}
    found = []
    if plan:
        for group_key, _, box in boxes(plan):
            for item in box["items"]:
                if item.get("pr") in open_prs:
                    found.append((box_key(group_key, box), f"pr:{item['pr']}", "plan"))
                if item.get("issue") in open_issues:
                    found.append((box_key(group_key, box), f"issue:{item['issue']}", "plan"))
    for pr in open_prs.values():
        for number in closes(pr, data["repo"]):
            if number in open_issues:
                found.append((f"issue:{number}", f"pr:{pr['number']}", "closes"))
    for issue in data["open_issues"]:
        parent = (issue.get("parent") or {}).get("number")
        if parent in open_issues and closes({"closingIssuesReferences": [issue["parent"]]}, data["repo"]):
            found.append((f"issue:{parent}", f"issue:{issue['number']}", "sub"))
        for blocker in (issue.get("blockedBy") or {}).get("nodes") or []:
            if blocker.get("number") in open_issues and closes({"closingIssuesReferences": [blocker]}, data["repo"]):
                found.append((f"issue:{blocker['number']}", f"issue:{issue['number']}", "blocks"))
    # A fork's branch named main is not this repo's main. Older saved data without
    # repository identity cannot prove a stack, so omit that inferred link.
    branches = {}
    for number, pr in open_prs.items():
        head = pr.get("headRepository") or {}
        owner = pr.get("headRepositoryOwner") or {}
        full_name = head.get("nameWithOwner") or f"{owner.get('login', '')}/{head.get('name', '')}"
        if full_name.lower() == data["repo"].lower():
            branches[pr["headRefName"]] = number
    for number, pr in open_prs.items():
        base = branches.get(pr["baseRefName"])
        if base is not None and base != number:
            found.append((f"pr:{base}", f"pr:{number}", "stacked"))
    return list(dict.fromkeys(found))  # drop repeats, keep order


def clusters(links: list[tuple[str, str, str]]) -> list[list[str]]:
    """Group linked keys into clusters: two keys share a cluster if a path of links joins them.

    Each cluster keeps the order its keys were first seen in, and the clusters keep the
    order of their first key, so the page reads in plan order.
    """
    cluster_of: dict[str, int] = {}
    members: list[list[str]] = []
    for a, b, _ in links:
        ca, cb = cluster_of.get(a), cluster_of.get(b)
        if ca is None and cb is None:
            cluster_of[a] = cluster_of[b] = len(members)
            members.append([a, b])
        elif cb is None:
            cluster_of[b] = ca
            members[ca].append(b)
        elif ca is None:
            cluster_of[a] = cb
            members[cb].append(a)
        elif ca != cb:  # this link joins two clusters: move the later one into the earlier one
            keep, gone = min(ca, cb), max(ca, cb)
            for key in members[gone]:
                cluster_of[key] = keep
            members[keep] += members[gone]
            members[gone] = []
    return [m for m in members if m]


def layout(
    groups: list[list[str]],
) -> tuple[dict[str, tuple[float, float]], list[tuple], float, float]:
    """Where each node goes.

    A column nothing uses (no plan, say, or no linked issues) is left out, so the
    other columns move closer together.

    Returns:
        The top-left corner of each node by key, each cluster's (keys, top, height),
        and the drawing's width and height.
    """
    kinds = {key.split(":")[0] for keys in groups for key in keys}
    used_columns = sorted(COLUMNS[kind] for kind in kinds)
    x_of = {column: MARGIN + i * (NODE_W + COL_GAP) for i, column in enumerate(used_columns)}
    places: dict[str, tuple[float, float]] = {}
    placed_clusters = []
    top = 0.0
    for keys in groups:
        columns: list[list[str]] = [[], [], []]
        for key in keys:
            columns[COLUMNS[key.split(":")[0]]].append(key)
        rows = max(len(column) for column in columns)
        height = rows * NODE_H + (rows - 1) * ROW_GAP
        for index, column in enumerate(columns):
            used = len(column) * NODE_H + (len(column) - 1) * ROW_GAP
            y = top + (height - used) / 2  # centre a short column next to a tall one
            for key in column:
                places[key] = (x_of[index], y)
                y += NODE_H + ROW_GAP
        placed_clusters.append((keys, top, height))
        top += height + CLUSTER_GAP
    width = 2 * MARGIN + len(used_columns) * NODE_W + (len(used_columns) - 1) * COL_GAP
    return places, placed_clusters, width, max(top - CLUSTER_GAP, 0)


def path(a: tuple[float, float], b: tuple[float, float]) -> str:
    """An SVG path for a link from node a to node b (both top-left corners).

    Between columns, a curve from a's right side to b's left side. Inside one column,
    an arc that bulges out to the right, so it does not run over the nodes between.
    """
    ay, by = a[1] + NODE_H / 2, b[1] + NODE_H / 2
    if a[0] == b[0]:
        x = a[0] + NODE_W
        return f"M{x:.0f} {ay:.0f}C{x + 45:.0f} {ay:.0f} {x + 45:.0f} {by:.0f} {x:.0f} {by:.0f}"
    x1, x2 = a[0] + NODE_W, b[0]
    mid = (x2 - x1) / 2
    return f"M{x1:.0f} {ay:.0f}C{x1 + mid:.0f} {ay:.0f} {x2 - mid:.0f} {by:.0f} {x2:.0f} {by:.0f}"
