"""The graph: which links it finds, how it clusters them, and that nodes never overlap."""

from itertools import combinations

from conftest import issue, pr

import dashboard_graph as graph


def test_every_kind_of_link_is_found(demo_plan: dict, demo_data: dict) -> None:
    links = set(graph.edges(demo_plan, demo_data))
    assert ("box:app/Shopping list", "pr:41", "plan") in links
    assert ("box:app/Shopping list", "issue:13", "plan") in links
    assert ("issue:13", "pr:41", "closes") in links
    assert ("issue:12", "issue:13", "sub") in links
    assert ("issue:16", "issue:17", "blocks") in links
    assert ("pr:42", "pr:43", "stacked") in links


def test_closed_work_is_left_out(demo_plan: dict, demo_data: dict) -> None:
    keys = {k for a, b, _ in graph.edges(demo_plan, demo_data) for k in (a, b)}
    assert "pr:39" not in keys  # merged, though the plan still points at it
    assert "pr:38" not in keys  # closed without merging


def test_without_a_plan_only_github_links_are_drawn(demo_data: dict) -> None:
    links = graph.edges(None, demo_data)
    assert links
    assert not any(a.startswith("box:") for a, _, _ in links)


def test_a_link_is_listed_once_even_if_two_things_say_it(data: dict) -> None:
    data["open_prs"].append(pr(11, "a", closingIssuesReferences=[{"number": 20}, {"number": 20}]))
    links = graph.edges(None, data)
    assert links.count(("issue:20", "pr:11", "closes")) == 1


def test_clusters_join_through_shared_nodes_and_keep_first_seen_order() -> None:
    links = [("a:1", "b:1", "x"), ("c:1", "d:1", "x"), ("b:1", "d:1", "x"), ("e:1", "f:1", "x")]
    assert graph.clusters(links) == [["a:1", "b:1", "c:1", "d:1"], ["e:1", "f:1"]]


def test_nodes_never_overlap_and_kinds_sit_in_their_own_columns(demo_plan: dict, demo_data: dict) -> None:
    places, placed, width, height = graph.layout(graph.clusters(graph.edges(demo_plan, demo_data)))
    for (_, a), (_, b) in combinations(places.items(), 2):
        apart_x = abs(a[0] - b[0]) >= graph.NODE_W
        apart_y = abs(a[1] - b[1]) >= graph.NODE_H
        assert apart_x or apart_y
    xs = {kind: {x for key, (x, _) in places.items() if key.startswith(kind)} for kind in ("box", "issue", "pr")}
    assert all(len(found) == 1 for found in xs.values())
    assert max(xs["box"]) < min(xs["issue"]) < min(xs["pr"])
    assert all(x + graph.NODE_W <= width for x, _ in places.values())
    assert all(y + graph.NODE_H <= height for _, y in places.values())


def test_an_unused_column_is_dropped() -> None:
    links = [("issue:1", "pr:2", "closes")]
    places, _, width, _ = graph.layout(graph.clusters(links))
    assert places["issue:1"][0] == graph.MARGIN
    assert width == 2 * graph.MARGIN + 2 * graph.NODE_W + graph.COL_GAP


def test_paths_start_and_end_on_the_node_edges() -> None:
    across = graph.path((0, 0), (400, 100))
    assert across.startswith(f"M{graph.NODE_W} {graph.NODE_H // 2}")
    assert across.endswith(f"400 {100 + graph.NODE_H // 2}")
    same_column = graph.path((0, 0), (0, 100))
    assert same_column.startswith(f"M{graph.NODE_W} ")
    assert same_column.endswith(f"{graph.NODE_W} {100 + graph.NODE_H // 2}")


def test_an_issue_blocked_by_a_closed_issue_has_no_link(data: dict) -> None:
    data["open_issues"].append(issue(21, blockedBy={"nodes": [{"number": 99}]}))
    assert graph.edges(None, data) == []
