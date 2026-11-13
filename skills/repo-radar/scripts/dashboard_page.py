"""Draw the dashboard: one HTML file with everything inside it, nothing loaded from outside.

The page has up to five tabs: Plan (only when the repo has a plan), Pull requests,
Issues, Graph, and Done. Python writes all of the HTML; the small script at the end
only switches tabs, filters by the search box, and switches light and dark mode.

Every piece of text from GitHub goes through _e(), which escapes it, so a pull
request titled "<script>" shows as text and never runs.
"""

from html import escape
from typing import Any

import dashboard_github as github
import dashboard_graph as graph
import dashboard_plan as plans

ITEM_ICONS = {"built": "check", "simulated": "half", "pr": "dot", "missing": "ring"}
ITEM_LABELS = {
    "built": "Built on main",
    "simulated": "On main, but a stub or fake",
    "pr": "In an open pull request",
    "missing": "Not built yet",
}
BOX_CLASSES = {"Built": "green", "In review": "blue", "Partly built": "yellow", "Not built": ""}
PR_CLASSES = {"ready": "green", "review": "blue", "author": "orange", "failing": "red", "draft": ""}
EDGE_LABELS = {
    "plan": "on the plan",
    "closes": "PR closes issue",
    "sub": "sub-issue",
    "blocks": "blocked by",
    "stacked": "PR built on another PR",
}


def _e(text: Any) -> str:
    """Escape text for HTML."""
    return escape(str(text), quote=True)


def _href(url: Any) -> str:
    """A link target, only if it is a web address; anything else becomes "#"."""
    url = str(url or "")
    return _e(url) if url.startswith(("https://", "http://")) else "#"


def _a(url: Any, text: Any, cls: str = "") -> str:
    attr = f' class="{cls}"' if cls else ""
    return f'<a{attr} href="{_href(url)}" target="_blank" rel="noopener">{_e(text)}</a>'


def _pill(thing: dict[str, Any]) -> str:
    return _a(thing.get("url"), f"#{thing['number']}", "pill")


def _chip(text: Any, cls: str = "", tip: str = "") -> str:
    title = f' title="{_e(tip)}"' if tip else ""
    return f'<span class="chip {cls}"{title}>{_e(text)}</span>'


def _person(login: str) -> str:
    """@login, linked to the person (or app) on GitHub."""
    path = f"apps/{login[4:]}" if login.startswith("app/") else login
    return _a(f"https://github.com/{path}", f"@{login.removeprefix('app/')}", "handle")


def _search(*parts: Any) -> str:
    return _e(" ".join(str(p) for p in parts if p).lower())


def _tiles(pairs: list[tuple[Any, str]]) -> str:
    tiles = "".join(f'<div class="tile"><div class="num">{_e(n)}</div>{_e(t)}</div>' for n, t in pairs)
    return f'<div class="tiles">{tiles}</div>'


def _section(title: str, sub: str, cards: str, is_open: bool = True) -> str:
    return (
        f'<details class="section"{" open" if is_open else ""}><summary><h2>{_e(title)}</h2>'
        f'<span class="sub">{_e(sub)}</span></summary><div class="grid">{cards}</div></details>'
    )


def _card(rows: list[str], cls: str = "", head: str = "", search: str = "", wide: bool = True) -> str:
    size = " wide" if wide else ""
    return (
        f'<div class="card {cls}{size}" data-search="{search}">{head}'
        f'<ul>{"".join(rows)}</ul></div>'
    )


def _ago(stamp: str, now: str) -> str:
    """ "today", or "3 days ago"."""
    age = github.age(stamp, now)
    return age if age == "today" else f"{age} ago"


def _labels(thing: dict[str, Any]) -> str:
    return "".join(_chip(label["name"], "label") for label in thing.get("labels") or [])


# ---------------------------------------------------------------- Plan tab


def _plan_item(item: dict[str, Any], prs: dict[int, dict[str, Any]], issue_urls: dict) -> str:
    """One item of a box: its marker, its PR or issue, its text, and any warning from GitHub."""
    parts = []
    if "pr" in item:
        pr = prs.get(item["pr"], {})
        parts.append(_pill({"number": item["pr"], "url": pr.get("url")}))
    if "issue" in item:
        parts.append(_a(issue_urls.get(item["issue"]), f"issue #{item['issue']}", "chip"))
    parts.append(_e(item["text"]))
    check = plans.pr_check(item, prs)
    if check:
        parts.append(_chip(check[0], "warn", check[1]))
    icon = ITEM_ICONS[item["status"]]
    return (
        f'<li class="item" data-search="{_search(item["text"], item.get("pr"), check and check[0])}">'
        f'<span class="icon {icon}" title="{ITEM_LABELS[item["status"]]}"></span>'
        f'<div>{" ".join(parts)}</div></li>'
    )


def _plan_tab(plan: dict[str, Any], data: dict[str, Any]) -> str:
    prs = github.all_prs(data)
    issue_urls = {i["number"]: i["url"] for i in data["open_issues"] + data["closed_issues"]}
    items = [item for _, _, box in plans.boxes(plan) for item in box["items"]]
    counts = {s: sum(i["status"] == s for i in items) for s in plans.STATUSES}
    warnings = sum(plans.pr_check(i, prs) is not None for i in items)
    out = [
        _tiles(
            [(len(items), "items on the plan")]
            + [(counts[s], ITEM_LABELS[s].lower()) for s in plans.STATUSES]
            + [(warnings, "PRs that merged or closed")]
        ),
        f'<p class="explain">{_e(plan["title"])}. Plan last refreshed: '
        f"{_e(' '.join(str(plan.get('as_of', 'not set')).split()))}. A yellow tag means GitHub "
        "disagrees with the plan: hover it for what to change at the weekly refresh.</p>",
        _legend(),
    ]
    for key, group in plan["groups"].items():
        cards = []
        for box in group["boxes"]:
            owner = plans.box_owner(group, box)
            status = plans.box_status(box["items"])
            note = plans.in_review_note(box["items"])
            owner_html = (
                f'<div class="owner">Owner: {_e(owner)}</div>'
                if owner
                else '<div class="owner unowned">Owner: not assigned</div>'
            )
            head = (
                f'<div class="card-head"><div><div class="card-title">{_e(box["title"])}</div>'
                f'{owner_html}</div><div class="status">{_e(status)}'
                f'{f"<br>{_e(note)}" if note else ""}</div></div>'
            )
            rows = [_plan_item(item, prs, issue_urls) for item in box["items"]]
            cls = BOX_CLASSES[status] or "dashed"
            search = _search(box["title"], owner or "not assigned", status)
            cards.append(_card(rows, cls, head, search, wide=False))
        owner = group.get("owner")
        sub = " · ".join(str(s) for s in [group.get("subtitle"), owner and f"owner: {owner}"] if s)
        out.append(_section(group["title"], sub, "".join(cards)))
    unplaced = plans.unplaced_prs(plan, data["open_prs"])
    if unplaced:
        rows = [_pr_row(pr, data, None) for pr in unplaced]
        out.append(
            _section(
                f"Open pull requests not on the plan ({len(unplaced)})",
                "add an item for each to the right box, or ask its author which box it belongs to",
                _card(rows, "yellow"),
            )
        )
    return "".join(out)


def _legend() -> str:
    markers = "".join(
        f'<span class="legend-item"><span class="icon {ITEM_ICONS[s]}"></span>{_e(ITEM_LABELS[s])}</span>'
        for s in plans.STATUSES
    )
    return f'<div class="legend">{markers}</div>'


# ---------------------------------------------------------------- Pull requests tab


def _plan_boxes_by_pr(plan: dict[str, Any] | None) -> dict[int, str]:
    if not plan:
        return {}
    return {
        item["pr"]: box["title"]
        for _, _, box in plans.boxes(plan)
        for item in box["items"]
        if "pr" in item
    }


def _pr_row(pr: dict[str, Any], data: dict[str, Any], on_plan: dict[int, str] | None) -> str:
    """One open pull request: number, title, and tags for what matters about it."""
    chips = []
    checks = github.checks_state(pr)
    if checks in ("failing", "pending"):
        chips.append(_chip(f"checks {checks}", "red" if checks == "failing" else ""))
    if "additions" in pr:
        size = f"+{pr['additions']} −{pr['deletions']}, {pr['changedFiles']} files"
        chips.append(_chip(size, "", "lines added, lines removed, files changed"))
    for number in github.closes(pr, data["repo"]):
        chips.append(_chip(f"closes #{number}", "link"))
    if on_plan is not None:
        box = on_plan.get(pr["number"])
        chips.append(_chip(f"plan: {box}", "link") if box else _chip("not on the plan", "warn"))
    login = pr["author"]["login"]
    return (
        f'<li class="item" data-search="{_search(pr["number"], pr["title"], login, pr.get("headRefName"))}">'
        f'<span class="icon dot"></span><div>{_pill(pr)} {_a(pr["url"], pr["title"], "title-link")} '
        f'{"".join(chips)}{_labels(pr)}<div class="people">by {_person(login)} · opened '
        f'{_e(_ago(pr["createdAt"], data["fetched_at"]))}</div></div></li>'
    )


def _prs_tab(plan: dict[str, Any] | None, data: dict[str, Any]) -> str:
    groups = github.grouped(data["open_prs"], github.pr_group, github.PR_GROUPS)
    on_plan = _plan_boxes_by_pr(plan) if plan else None
    out = [
        _tiles(
            [(len(data["open_prs"]), "open pull requests")]
            + [(len(groups[k]), github.PR_GROUPS[k][0].lower()) for k in github.PR_GROUPS]
        ),
        '<p class="explain">Sorted by facts GitHub has, in this order: draft, a failing check, '
        "changes requested, approved; anything else needs review. Oldest first.</p>",
    ]
    start = (groups["ready"] + groups["review"])[:5]
    if start:
        rows = [_pr_row(pr, data, on_plan) for pr in start]
        out.append(
            _section("Start here", "ready to merge first, then the longest-waiting reviews", _card(rows, "yellow"))
        )
    for key, (title, sub) in github.PR_GROUPS.items():
        if groups[key]:
            rows = [_pr_row(pr, data, on_plan) for pr in groups[key]]
            out.append(_section(f"{title} ({len(groups[key])})", sub, _card(rows, PR_CLASSES[key])))
    if not data["open_prs"]:
        out.append('<p class="explain">No open pull requests.</p>')
    return "".join(out)


# ---------------------------------------------------------------- Issues tab


def _issue_row(issue: dict[str, Any], data: dict[str, Any], prs_for_issue: dict, on_plan: dict) -> str:
    chips = [_chip(f"PR #{n}", "link") for n in prs_for_issue.get(issue["number"], [])]
    parent = (issue.get("parent") or {}).get("number")
    if parent:
        chips.append(_chip(f"sub-issue of #{parent}", "link"))
    for blocker in (issue.get("blockedBy") or {}).get("nodes") or []:
        chips.append(_chip(f"blocked by #{blocker.get('number')}", "red"))
    if issue["number"] in on_plan:
        chips.append(_chip(f"plan: {on_plan[issue['number']]}", "link"))
    login = issue["author"]["login"]
    assigned = " ".join(_person(a["login"]) for a in issue.get("assignees") or [])
    return (
        f'<li class="item" data-search="{_search(issue["number"], issue["title"], login, *[l["name"] for l in issue.get("labels") or []])}">'
        f'<span class="icon ring"></span><div>{_pill(issue)} '
        f'{_a(issue["url"], issue["title"], "title-link")} {"".join(chips)}{_labels(issue)}'
        f'<div class="people">by {_person(login)}{f" · assigned {assigned}" if assigned else ""}'
        f' · opened {_e(_ago(issue["createdAt"], data["fetched_at"]))}</div></div></li>'
    )


def _issues_tab(plan: dict[str, Any] | None, data: dict[str, Any]) -> str:
    prs_for_issue = github.issue_prs(data)
    groups = github.grouped(
        data["open_issues"], lambda i: github.issue_group(i, prs_for_issue), github.ISSUE_GROUPS
    )
    on_plan = {}
    if plan:
        on_plan = {
            item["issue"]: box["title"]
            for _, _, box in plans.boxes(plan)
            for item in box["items"]
            if "issue" in item
        }
    out = [
        _tiles(
            [(len(data["open_issues"]), "open issues")]
            + [(len(groups[k]), github.ISSUE_GROUPS[k][0].lower()) for k in github.ISSUE_GROUPS]
        ),
        '<p class="explain">Sorted by whether anyone is on it yet. Oldest first. '
        "Search for a label to see one area.</p>",
    ]
    for key, (title, sub) in github.ISSUE_GROUPS.items():
        if groups[key]:
            rows = [_issue_row(i, data, prs_for_issue, on_plan) for i in groups[key]]
            out.append(_section(f"{title} ({len(groups[key])})", sub, _card(rows)))
    if not data["open_issues"]:
        out.append('<p class="explain">No open issues.</p>')
    return "".join(out)


# ---------------------------------------------------------------- Graph tab


def _node(key: str, x: float, y: float, plan: dict[str, Any] | None, data: dict[str, Any]) -> tuple[str, str]:
    """One node of the graph, and the text the search box matches it by."""
    kind, _, ident = key.partition(":")
    if kind == "box":
        group_key, _, title = ident.partition("/")
        group = plan["groups"][group_key]
        box = next(b for b in group["boxes"] if b["title"] == title)
        status = plans.box_status(box["items"])
        owner = plans.box_owner(group, box) or "not assigned"
        line1, line2, url = title, f"Plan · {status} · {owner}", None
        cls = BOX_CLASSES[status] or "plain"
    elif kind == "issue":
        issue = next(i for i in data["open_issues"] if i["number"] == int(ident))
        line1 = f"#{ident} {issue['title']}"
        line2 = f"Issue · by @{issue['author']['login']}"
        url, cls = issue["url"], "issue"
    else:
        pr = next(p for p in data["open_prs"] if p["number"] == int(ident))
        group = github.pr_group(pr)
        line1 = f"#{ident} {pr['title']}"
        line2 = f"PR · {github.PR_GROUPS[group][0]} · @{pr['author']['login']}"
        url, cls = pr["url"], PR_CLASSES[group] or "plain"
    room = int((graph.NODE_W - 20) / 7)
    short = line1 if len(line1) <= room else line1[: room - 1] + "…"
    # A link is named by aria-label (the visible text is cut short). A plan box is not a
    # link, so it is a labelled image instead; either way screen readers get the full text.
    label = _e(f"{line1}, {line2}" + (", opens in a new tab" if url else ""))
    role = "" if url else f' role="img" aria-label="{label}"'
    body = (
        f'<g class="node {cls}"{role}><title>{_e(line1)}</title>'
        f'<rect x="{x:.0f}" y="{y:.0f}" width="{graph.NODE_W}" height="{graph.NODE_H}" rx="8"/>'
        f'<text x="{x + 10:.0f}" y="{y + 20:.0f}" class="n1">{_e(short)}</text>'
        f'<text x="{x + 10:.0f}" y="{y + 37:.0f}" class="n2">{_e(line2)}</text></g>'
    )
    if url:
        body = f'<a href="{_href(url)}" target="_blank" rel="noopener" aria-label="{label}">{body}</a>'
    return body, f"{line1} {line2}"


def _graph_tab(plan: dict[str, Any] | None, data: dict[str, Any]) -> str:
    links = graph.edges(plan, data)
    out = [
        '<p class="explain">How the open work links up. Plan boxes on the left, issues in the '
        "middle, pull requests on the right. Only links GitHub or the plan records are drawn, "
        "and closed work is left out. Hover a cluster to pick it out; click a node to open it.</p>"
    ]
    legend = "".join(
        f'<span class="legend-item"><svg width="28" height="10"><line class="edge {k}" x1="0" y1="5" '
        f'x2="28" y2="5"/></svg>{_e(label)}</span>'
        for k, label in EDGE_LABELS.items()
    )
    out.append(f'<div class="legend">{legend}</div>')
    if not links:
        out.append(
            '<p class="explain">Nothing links up yet. Links appear when a pull request says it '
            'closes an issue ("Closes #12"), an issue gets sub-issues or a "blocked by", a pull '
            "request is opened on another's branch, or a plan item names a PR or an issue.</p>"
        )
        return "".join(out)
    places, placed, w, height = graph.layout(graph.clusters(links))
    parts = []
    for keys, _, _ in placed:
        inside = set(keys)
        lines = [
            f'<path class="edge {kind}" aria-hidden="true" d="{graph.path(places[a], places[b])}"><title>{_e(EDGE_LABELS[kind])}</title></path>'
            for a, b, kind in links
            if a in inside
        ]
        nodes = [_node(k, *places[k], plan, data) for k in keys]
        search = _search(*(text for _, text in nodes))
        parts.append(
            f'<g class="cluster" data-search="{search}">{"".join(lines)}{"".join(n for n, _ in nodes)}</g>'
        )
    linked = {k for a, b, _ in links for k in (a, b)}
    lonely_prs = sum(f"pr:{p['number']}" not in linked for p in data["open_prs"])
    lonely_issues = sum(f"issue:{i['number']}" not in linked for i in data["open_issues"])
    out.append(
        f'<div class="graph-wrap"><svg class="graph" viewBox="0 0 {w:.0f} {height + 10:.0f}" '
        f'width="{w:.0f}" role="group" aria-label="Graph of open work">'
        '<defs aria-hidden="true"><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="arrowhead"/>'
        f'</marker></defs><g transform="translate(0 5)">{"".join(parts)}</g></svg></div>'
        f'<p class="note">Left out because nothing links to them: {lonely_prs} open pull '
        f"requests and {lonely_issues} open issues. They are on the other tabs.</p>"
    )
    return "".join(out)


# ---------------------------------------------------------------- Done tab


def _done_row(item: dict[str, Any], data: dict[str, Any]) -> str:
    if item["kind"] == "pr":
        good = item["state"] == "MERGED"
        what = "PR merged" if good else "PR closed without merging"
    else:
        good = item.get("stateReason") != "NOT_PLANNED"
        what = "issue closed" if good else "issue closed as not planned"
    login = item["author"]["login"]
    return (
        f'<li class="item" data-search="{_search(item["number"], item["title"], login, what)}">'
        f'<span class="icon {"check" if good else "cross"}" title="{_e(what)}"></span><div>'
        f'{_pill(item)} {_a(item["url"], item["title"], "title-link")} {_chip(what)}'
        f'<div class="people">by {_person(login)} · closed {_e(item["closedAt"][:10])}</div></div></li>'
    )


def _done_tab(data: dict[str, Any]) -> str:
    merged = sum(pr["state"] == "MERGED" for pr in data["closed_prs"])
    not_planned = sum(i.get("stateReason") == "NOT_PLANNED" for i in data["closed_issues"])
    out = [
        _tiles(
            [
                (merged, "PRs merged"),
                (len(data["closed_prs"]) - merged, "PRs closed without merging"),
                (len(data["closed_issues"]) - not_planned, "issues closed"),
                (not_planned, "issues not planned"),
            ]
        ),
        f'<p class="explain">The last {_e(data["days"])} days. '
        + (
            "Each sits under the first release published after it closed.</p>"
            if data["releases"]
            else "This repo has no releases, so they are grouped by the month they closed.</p>"
        ),
    ]
    for index, (name, items) in enumerate(github.done_groups(data)):
        prs = [i for i in items if i["kind"] == "pr"]
        sub = (
            f"{sum(p['state'] == 'MERGED' for p in prs)} PRs merged, "
            f"{len(items) - len(prs)} issues closed"
        )
        rows = [_done_row(i, data) for i in items]
        out.append(_section(name, sub, _card(rows, "green"), is_open=index < 3))
    if not data["closed_prs"] and not data["closed_issues"]:
        out.append('<p class="explain">Nothing closed in this time.</p>')
    return "".join(out)


# ---------------------------------------------------------------- The page


def _page(title: str, header: str, main: str) -> str:
    """The parts every page shares: head, styles, search, theme button, and script."""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_e(title)}</title><style>{CSS}</style>{THEME_SCRIPT}</head><body>"
        f"<header>{header}"
        '<input id="search" type="search" placeholder="Search titles, people, labels…" aria-label="Search">'
        '<button id="theme" type="button">Dark mode</button></header>'
        f'<main>{main}<p id="no-results" role="status" hidden>No matches. Try a different search.</p></main>'
        '<footer class="note">Made by repo-radar. The page is rebuilt from GitHub; '
        "do not edit it by hand.</footer>"
        f"<script>{PAGE_SCRIPT}</script></body></html>\n"
    )


def render(data: dict[str, Any], plan: dict[str, Any] | None, back: str | None = None) -> str:
    """The whole page for one repo, as an HTML string.

    back: the overview page's file name, when this page is one of several being watched.
    """
    tabs = []
    if plan:
        tabs.append(("plan", "Plan", _plan_tab(plan, data)))
    tabs += [
        ("prs", f"Pull requests ({len(data['open_prs'])})", _prs_tab(plan, data)),
        ("issues", f"Issues ({len(data['open_issues'])})", _issues_tab(plan, data)),
        ("graph", "Graph", _graph_tab(plan, data)),
        ("done", "Done", _done_tab(data)),
    ]
    buttons = "".join(
        f'<button type="button" role="tab" id="tab-{key}" aria-controls="{key}" aria-selected="{str(i == 0).lower()}" tabindex="{0 if i == 0 else -1}" data-tab="{key}"{" class=active" if i == 0 else ""}>{_e(label)}</button>'
        for i, (key, label, _) in enumerate(tabs)
    )
    panels = "".join(
        f'<section role="tabpanel" aria-labelledby="tab-{key}" tabindex="0" class="tab{" active" if i == 0 else ""}" id="{key}">{body}</section>'
        for i, (key, _, body) in enumerate(tabs)
    )
    built = data["fetched_at"].replace("T", " ").removesuffix("Z")
    header = (
        (f'<a class="back" href="{_e(back)}">← Manager overview</a>' if back else "")
        + f'<h1>{_a(data["url"], data["repo"], "title-link")}</h1>'
        f'<span class="note">from GitHub, {_e(built)} UTC</span>'
        f'<nav class="tabs" role="tablist" aria-label="Repository views">{buttons}</nav>'
    )
    warnings = "".join(f'<p class="explain">{_e(w)}</p>' for w in data.get("warnings", []))
    return _page(f"{data['repo']} dashboard", header, warnings + panels)


# ---------------------------------------------------------------- The overview (watch list)


def _count(n: Any, cls: str = "") -> str:
    """A number in the overview table, coloured only when it is not zero."""
    return f'<td class="num">{_chip(n, cls) if n and cls else _e(n)}</td>'


def _unavailable_note(missing: int, readable: int) -> str:
    """Say how many watched repos could not be read, with singular and plural right."""
    repos = "repo" if missing == 1 else "repos"
    readable_repos = "readable repo" if readable == 1 else "readable repos"
    return f"{missing} {repos} unavailable. Totals include only the {readable} {readable_repos}."


def render_index(rows: list[dict[str, Any]], built_at: str) -> str:
    """The overview page for a watch list: one row per repo, linking to its page."""
    good = [r for r in rows if not r.get("error")]
    total = lambda key: sum(r[key] for r in good)  # noqa: E731
    tiles = _tiles(
        [
            (len(rows), "repos watched"),
            (total("open_prs"), "open pull requests"),
            (total("ready"), "ready to merge"),
            (total("failing"), "with checks failing"),
            (total("nobody"), "open issues nobody is on"),
        ]
    )
    head = (
        "<tr><th>Repo</th><th>Open PRs</th><th>Ready to merge</th><th>Needs review</th>"
        "<th>Checks failing</th><th>Open issues</th><th>Nobody on it</th><th>Plan built</th>"
        "<th>Plan to update</th><th>Last activity</th></tr>"
    )
    body = []
    for r in rows:
        name = f'<td class="repo">{_a(r["url"], r["repo"], "title-link")}'
        if r.get("error"):
            body.append(
                f'<tr data-search="{_search(r["repo"])}">{name}</td>'
                f'<td colspan="9" class="error">Could not read it: {_e(r["error"])}</td></tr>'
            )
            continue
        name += f'<br><a href="{_e(r["page"])}">View repo dashboard →</a></td>'
        plan = r["plan"]
        plan_cells = (
            f'<td class="num">{plan["built"]} of {plan["items"]}</td>' + _count(plan["to_update"], "warn")
            if plan
            else '<td class="num note">no plan</td><td class="num note">—</td>'
        )
        newest = _ago(r["newest"], built_at) if r["newest"] else "none"
        body.append(
            f'<tr data-search="{_search(r["repo"])}">{name}'
            + _count(r["open_prs"])
            + _count(r["ready"], "green")
            + _count(r["review"])
            + _count(r["failing"], "red")
            + _count(r["open_issues"])
            + _count(r["nobody"])
            + plan_cells
            + f'<td class="num">{_e(newest)}</td></tr>'
        )
    main = (
        '<section class="tab active" id="overview">'
        + (f'<p class="explain">{_unavailable_note(len(rows) - len(good), len(good))}</p>' if len(good) != len(rows) else "")
        + tiles
        + '<p class="explain">Each repo has its own page with its pull requests, issues, graph, '
        "and plan. A yellow number under Plan to update counts items whose pull request has "
        "merged or closed, so the plan needs its weekly refresh.</p>"
        + f'<div class="table-wrap"><table class="overview"><thead>{head}</thead>'
        + f'<tbody>{"".join(body)}</tbody></table></div></section>'
    )
    built = built_at.replace("T", " ").removesuffix("Z")
    header = f'<h1>repo-radar · Manager overview</h1><span class="note">{len(rows)} repos, from GitHub, {_e(built)} UTC</span>'
    return _page("repo-radar overview", header, main)


CSS = """
:root{--bg:#fff;--fg:#1f2328;--muted:#57606a;--faint:#8c959f;--line:#e5e7eb;--dash:#c9ced6;
--section-bg:#fbfcfd;--card-bg:#fff;--btn-bg:#f6f8fa;--btn-line:#d0d7de;--accent:#1d4ed8;
--accent-fg:#fff;--link:#0969da;--owner:#4338ca;--unowned:#b42318;
--green-line:#4ac26b;--green-bg:#f0fbf3;--blue-line:#54aeff;--blue-bg:#eef6ff;
--yellow-line:#e3b341;--yellow-bg:#fffaeb;--orange-line:#f0883e;--orange-bg:#fff4ec;
--red-line:#f85149;--red-bg:#fff0ef;--purple:#8250df;--done:#1a7f37;--gold:#bf8700;
--warn-fg:#9a6700;--warn-bg:#fff8c5;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0d1117;--fg:#e6edf3;
--muted:#9da7b3;--faint:#7d8590;--line:#30363d;--dash:#3d444d;--section-bg:#11161d;--card-bg:#161b22;
--btn-bg:#21262d;--btn-line:#3d444d;--accent:#2f6feb;--link:#58a6ff;--owner:#a5b4fc;--unowned:#ff7b72;
--green-line:#2ea043;--green-bg:#12261a;--blue-line:#1f6feb;--blue-bg:#121d2f;--yellow-line:#9e6a03;
--yellow-bg:#272115;--orange-line:#bd561d;--orange-bg:#2a1b12;--red-line:#da3633;--red-bg:#2b1517;
--purple:#bc8cff;--done:#3fb950;--gold:#d29922;--warn-fg:#e3b341;--warn-bg:#2e2510;color-scheme:dark}}
:root[data-theme=dark]{--bg:#0d1117;--fg:#e6edf3;--muted:#9da7b3;--faint:#7d8590;--line:#30363d;
--dash:#3d444d;--section-bg:#11161d;--card-bg:#161b22;--btn-bg:#21262d;--btn-line:#3d444d;
--accent:#2f6feb;--link:#58a6ff;--owner:#a5b4fc;--unowned:#ff7b72;--green-line:#2ea043;
--green-bg:#12261a;--blue-line:#1f6feb;--blue-bg:#121d2f;--yellow-line:#9e6a03;--yellow-bg:#272115;
--orange-line:#bd561d;--orange-bg:#2a1b12;--red-line:#da3633;--red-bg:#2b1517;--purple:#bc8cff;
--done:#3fb950;--gold:#d29922;--warn-fg:#e3b341;--warn-bg:#2e2510;color-scheme:dark}
body{font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif;margin:0;background:var(--bg);
color:var(--fg);font-size:14px}
[hidden]{display:none!important}
header{padding:14px 24px;border-bottom:1px solid var(--line);display:flex;gap:10px 18px;
align-items:center;flex-wrap:wrap}
header h1{font-size:20px;margin:0;overflow-wrap:anywhere}
a:focus-visible,button:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:3px}
.tabs{display:flex;flex-wrap:wrap;gap:6px}
.tabs button,#theme{border:1px solid var(--btn-line);background:var(--btn-bg);color:var(--fg);
padding:6px 12px;border-radius:6px;cursor:pointer;font-size:14px}
.tabs button.active{background:var(--accent);color:var(--accent-fg);border-color:var(--accent)}
#search{padding:6px 10px;border:1px solid var(--btn-line);border-radius:6px;width:260px;
max-width:100%;box-sizing:border-box;background:var(--card-bg);color:var(--fg)}
main{padding:16px 24px}
footer{padding:0 24px 24px}
.tab{display:none}.tab.active{display:block}
.tiles{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px}
.tile{border:1px solid var(--line);border-radius:8px;padding:8px 14px;min-width:96px;
color:var(--muted);background:var(--card-bg)}
.tile .num{font-size:22px;font-weight:600;color:var(--fg)}
.explain{color:var(--muted);margin:6px 0 12px;max-width:900px}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;margin:0 0 14px;color:var(--muted)}
.legend-item{display:inline-flex;align-items:center;gap:6px}
.section{border:1.5px dashed var(--dash);border-radius:12px;padding:10px 12px;
background:var(--section-bg);margin-bottom:12px}
.section h2{font-size:18px;margin:0;display:inline}
.sub{color:var(--muted);margin-left:10px}
summary{cursor:pointer;list-style:none}summary::-webkit-details-marker{display:none}
summary h2::before{content:"\\25B8  ";font-size:13px;color:var(--muted)}
details[open]>summary h2::before{content:"\\25BE  "}
.grid{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-start;margin-top:10px}
.card{box-sizing:border-box;flex:1 1 300px;max-width:520px;border:1.5px solid var(--line);
border-radius:8px;padding:8px 10px;background:var(--card-bg)}
.card.wide{max-width:none;flex-basis:100%}
.card.dashed{border-style:dashed;border-color:var(--faint)}
.card.green{border-color:var(--green-line);background:var(--green-bg)}
.card.blue{border-color:var(--blue-line);background:var(--blue-bg)}
.card.yellow{border-color:var(--yellow-line);background:var(--yellow-bg)}
.card.orange{border-color:var(--orange-line);background:var(--orange-bg)}
.card.red{border-color:var(--red-line);background:var(--red-bg)}
.card-head{display:flex;justify-content:space-between;gap:8px}
.card-title{font-weight:600;font-size:15px}
.owner{color:var(--owner);font-weight:600;font-size:12px;margin-top:2px}
.owner.unowned{color:var(--unowned)}
.status{color:var(--muted);font-size:12px;text-align:right;white-space:nowrap}
ul{list-style:none;padding:0;margin:6px 0 0}
.item>div{min-width:0;overflow-wrap:anywhere}
.item{display:flex;gap:8px;margin:6px 0;line-height:1.4}
.icon{flex:none;box-sizing:border-box;width:13px;height:13px;border-radius:50%;margin-top:3px;
border:1.5px solid var(--faint);display:inline-block}
.icon.dot{background:var(--link);border-color:var(--link)}
.icon.half{background:linear-gradient(90deg,var(--gold) 50%,transparent 50%);border-color:var(--gold)}
.icon.check{background:var(--done);border-color:var(--done)}
.icon.cross{background:var(--line);border-color:var(--faint)}
.pill{background:var(--accent);color:var(--accent-fg);border-radius:10px;padding:0 7px;
font-size:12px;font-weight:600;text-decoration:none}
.chip{display:inline-block;border-radius:10px;padding:0 6px;font-size:11px;margin:0 2px;
border:1px solid var(--btn-line);color:var(--muted);text-decoration:none;white-space:nowrap}
.chip.link{color:var(--link);border-color:var(--blue-line)}
.chip.warn{border-color:var(--gold);color:var(--warn-fg);background:var(--warn-bg);cursor:help}
.chip.red{border-color:var(--red-line);color:var(--unowned)}
.chip.label{color:var(--purple);border-color:var(--purple)}
.note{color:var(--muted);font-size:12px}
.people{font-size:12px;color:var(--muted)}
a{color:var(--link)}
.title-link{color:inherit;text-decoration:none}
.title-link:hover{color:var(--link);text-decoration:underline}
.handle{color:var(--owner);font-weight:600;text-decoration:none}
.graph-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--section-bg)}
.graph{display:block;min-width:700px;max-width:100%;height:auto;font-family:inherit}
.graph .cluster{transition:opacity .15s}
.graph:hover .cluster{opacity:.3}.graph .cluster:hover{opacity:1}
.graph .cluster.dim{opacity:.12}
.node rect{fill:var(--card-bg);stroke:var(--faint);stroke-width:1.5}
.node.green rect{fill:var(--green-bg);stroke:var(--green-line)}
.node.blue rect{fill:var(--blue-bg);stroke:var(--blue-line)}
.node.yellow rect{fill:var(--yellow-bg);stroke:var(--yellow-line)}
.node.orange rect{fill:var(--orange-bg);stroke:var(--orange-line)}
.node.red rect{fill:var(--red-bg);stroke:var(--red-line)}
.node.issue rect{stroke:var(--purple)}
.node .n1{font-size:13px;font-weight:600;fill:var(--fg)}
.node .n2{font-size:11px;fill:var(--muted)}
.graph a:hover rect{stroke-width:2.5}
.edge{fill:none;stroke-width:1.6;marker-end:url(#arrow)}
line.edge{marker-end:none;stroke-width:2}
.arrowhead{fill:var(--faint)}
.edge.plan{stroke:var(--faint)}
.edge.closes{stroke:var(--done)}
.edge.sub{stroke:var(--purple)}
.edge.blocks{stroke:var(--red-line);stroke-dasharray:5 4}
.edge.stacked{stroke:var(--orange-line)}
.back{font-size:14px;text-decoration:none}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--card-bg)}
.overview{border-collapse:collapse;width:100%;font-size:14px}
.overview th{text-align:left;font-size:12px;color:var(--muted);font-weight:600;padding:10px 12px;
border-bottom:1px solid var(--line);white-space:nowrap}
.overview td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
.overview tr:last-child td{border-bottom:none}
.overview .num{text-align:center;white-space:nowrap}
.overview .repo{font-weight:600}.overview .repo a:not(.title-link){font-weight:400;font-size:12px}
.overview .error{color:var(--unowned)}
.chip.green{border-color:var(--green-line);color:var(--done)}
@media (max-width:640px){header,main{padding-left:16px;padding-right:16px}.sub{display:block;margin:2px 0 0}}
@media print{.tabs,#search,#theme{display:none}.tab{display:block!important}.tab+.tab{break-before:page}
.card,.section{break-inside:avoid}}
"""

THEME_SCRIPT = """<script>
try{var t=localStorage.getItem('repo-radar-theme');if(t)document.documentElement.dataset.theme=t;}catch(e){}
</script>"""

PAGE_SCRIPT = """
const tabButtons = document.querySelectorAll('.tabs button');
const searchBox = document.getElementById('search');
const themeButton = document.getElementById('theme');

tabButtons.forEach(button => button.addEventListener('click', () => {
  tabButtons.forEach(b => {
    b.classList.toggle('active', b === button);
    b.setAttribute('aria-selected', String(b === button));
    b.tabIndex = b === button ? 0 : -1;
  });
  document.querySelectorAll('.tab').forEach(tab => tab.classList.toggle('active', tab.id === button.dataset.tab));
  applySearch();
}));

tabButtons.forEach((button, index) => button.addEventListener('keydown', event => {
  const keys = ['ArrowLeft', 'ArrowRight', 'Home', 'End'];
  if (!keys.includes(event.key)) return;
  event.preventDefault();
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabButtons.length - 1 :
    (index + (event.key === 'ArrowRight' ? 1 : -1) + tabButtons.length) % tabButtons.length;
  tabButtons[next].click();
  tabButtons[next].focus();
}));

// Show only the rows that match the search, and the cards and sections that still have one.
function applySearch() {
  const query = searchBox.value.trim().toLowerCase();
  const tab = document.querySelector('.tab.active');
  tab.querySelectorAll('.card').forEach(card => {
    const cardMatches = query === '' || card.dataset.search.includes(query);
    let anyRow = false;
    card.querySelectorAll('li[data-search]').forEach(row => {
      const show = cardMatches || row.dataset.search.includes(query);
      row.hidden = !show;
      anyRow = anyRow || show;
    });
    card.hidden = !(cardMatches || anyRow);
  });
  tab.querySelectorAll('.section').forEach(section => {
    const anyCard = [...section.querySelectorAll('.card')].some(card => !card.hidden);
    section.hidden = !anyCard;
    if (query !== '' && anyCard) section.open = true;
  });
  tab.querySelectorAll('tr[data-search]').forEach(row => {
    row.hidden = query !== '' && !row.dataset.search.includes(query);
  });
  tab.querySelectorAll('.cluster').forEach(cluster => {
    cluster.classList.toggle('dim', query !== '' && !cluster.dataset.search.includes(query));
  });
  const matches = [...tab.querySelectorAll('li[data-search], tr[data-search], .cluster')]
    .some(el => !el.hidden && !el.classList.contains('dim'));
  document.getElementById('no-results').hidden = query === '' || matches;
}
searchBox.addEventListener('input', applySearch);

function isDark() {
  const chosen = document.documentElement.dataset.theme;
  return chosen ? chosen === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
}
function showTheme() { themeButton.textContent = isDark() ? 'Light mode' : 'Dark mode'; }
themeButton.addEventListener('click', () => {
  const next = isDark() ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('repo-radar-theme', next); } catch (e) {}
  showTheme();
});
showTheme();
"""
