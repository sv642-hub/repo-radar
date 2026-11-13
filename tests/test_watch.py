"""Watching several repos: the watch list, the overview page, and the watching repo's setup."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import DEMO, SCRIPTS

import dashboard
import dashboard_page as page
import dashboard_watch as watching

DEMO_REPO = "example-org/pantry-planner"


def test_a_watch_list_takes_plain_names_and_names_with_a_plan() -> None:
    entries = watching.load_watch_list(
        "repos:\n  - a/one\n  - repo: b/two\n    plan: docs/arch.yaml\n"
    )
    assert entries == [{"repo": "a/one", "plan": None}, {"repo": "b/two", "plan": "docs/arch.yaml"}]


@pytest.mark.parametrize(
    "text, message",
    [
        ("repos: []", "at least one repo"),
        ("other: 1", "at least one repo"),
        ("repos:\n  - just-a-name", "owner/name"),
        ("repos:\n  - ../../etc/passwd", "owner/name"),
        ("repos:\n  - a/b c", "owner/name"),
        ("repos:\n  - a/one\n  - A/One", "listed twice"),
        ("repos:\n  - {repo: a/one, branch: x}", "only repo and plan"),
        ("repos: [unclosed", "not valid YAML"),
    ],
)
def test_a_bad_watch_list_is_refused_with_a_message_naming_it(text: str, message: str) -> None:
    with pytest.raises(watching.WatchListError, match=message):
        watching.load_watch_list(text)


def test_page_names_are_safe_file_names() -> None:
    assert watching.page_name("sv642-hub/app.v2") == "sv642-hub__app.v2.html"


def test_the_summary_counts_match_the_repo_page(demo_data: dict, demo_plan: dict) -> None:
    row = watching.summary(DEMO_REPO, demo_data, demo_plan)
    assert (row["open_prs"], row["ready"], row["review"], row["failing"]) == (8, 1, 4, 1)
    assert (row["open_issues"], row["nobody"]) == (9, 5)
    assert row["plan"] == {"built": 6, "items": 17, "to_update": 2}
    assert row["newest"] == "2026-11-11T21:00:00Z"


def _fakes(plans: dict[str, str | None], failing: set[str] = frozenset()) -> tuple[Any, Any, list]:
    """A get_plan and get_data that use the demo data, and a log of what was asked for."""
    asked: list = []

    def get_plan(repo: str, path: str) -> str | None:
        asked.append(("plan", repo, path))
        return plans.get(repo)

    def get_data(repo: str, extra: set[int]) -> dict[str, Any]:
        asked.append(("data", repo, extra))
        if repo in failing:
            raise RuntimeError("gh: Could not resolve to a Repository")
        data = json.loads((DEMO / "data.json").read_text(encoding="utf-8"))
        return {**data, "repo": repo, "url": f"https://github.com/{repo}"}

    return get_plan, get_data, asked


def test_watch_builds_each_page_and_one_failure_does_not_stop_the_rest() -> None:
    plan_text = (DEMO / "plan.yaml").read_text(encoding="utf-8")
    get_plan, get_data, asked = _fakes({"a/one": plan_text}, failing={"b/gone"})
    entries = watching.load_watch_list("repos: [a/one, b/gone, c/three]")
    pages, rows = watching.watch(entries, get_plan, get_data, page.render)
    assert set(pages) == {"a__one.html", "c__three.html"}
    assert [r["repo"] for r in rows] == ["a/one", "b/gone", "c/three"]
    assert "Could not resolve" in rows[1]["error"]
    assert rows[0]["plan"] and rows[2]["plan"] is None
    assert ("plan", "a/one", "docs/plan.yaml") in asked  # the default place
    assert ("data", "a/one", {38, 39, 41, 42, 44, 45, 47}) in asked  # the plan's PRs are fetched too


def test_a_plan_path_that_does_not_exist_is_reported_not_ignored() -> None:
    get_plan, get_data, _ = _fakes({})
    entries = watching.load_watch_list("repos:\n  - {repo: a/one, plan: docs/arch.yaml}")
    _, rows = watching.watch(entries, get_plan, get_data, page.render)
    assert rows[0]["error"] == "a/one: no file at docs/arch.yaml"


def test_a_broken_plan_in_one_repo_is_reported_on_its_row() -> None:
    get_plan, get_data, _ = _fakes({"a/one": "title: x\ngroups: {}\n"})
    _, rows = watching.watch(watching.load_watch_list("repos: [a/one]"), get_plan, get_data, page.render)
    assert "missing top-level key 'groups'" in rows[0]["error"]


def test_the_overview_links_each_page_and_escapes_errors(demo_data: dict, demo_plan: dict) -> None:
    rows = [
        watching.summary(DEMO_REPO, demo_data, demo_plan),
        {"repo": "b/gone", "url": "https://github.com/b/gone", "error": "<script>x</script>"},
    ]
    html = page.render_index(rows, "2026-11-12T08:00:00Z")
    assert 'href="example-org__pantry-planner.html"' in html
    assert "6 of 17" in html
    assert "&lt;script&gt;x" in html and "<script>x" not in html
    assert "2 repos, from GitHub, 2026-11-12 08:00:00 UTC" in html
    assert "today ago" not in html and ">today<" in html  # the newest activity was 11 hours before


def test_a_watched_page_links_back_to_the_overview(demo_data: dict) -> None:
    assert '<a class="back" href="index.html">' in page.render(demo_data, None, back="index.html")
    assert 'class="back"' not in page.render(demo_data, None)


def test_the_watch_command_writes_the_pages_from_saved_data(tmp_path: Path) -> None:
    saved = tmp_path / "saved"
    saved.mkdir()
    data = json.loads((DEMO / "data.json").read_text(encoding="utf-8"))
    (saved / "example-org__pantry-planner.json").write_text(json.dumps(data), encoding="utf-8")
    shutil.copyfile(DEMO / "plan.yaml", saved / "example-org__pantry-planner.plan.yaml")
    (tmp_path / "watchlist.yaml").write_text("repos: [example-org/pantry-planner, x/missing]\n")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "dashboard.py"), "watch", "--data-dir", str(saved), "--out", "site"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "could not read: x/missing" in result.stderr
    assert sorted(p.name for p in (tmp_path / "site").iterdir()) == [
        "example-org__pantry-planner.html",
        "index.html",
    ]
    assert 'data-tab="plan"' in (tmp_path / "site/example-org__pantry-planner.html").read_text()


def test_init_watch_writes_the_scripts_the_list_and_the_action(tmp_path: Path) -> None:
    written = dashboard.init_watch(tmp_path, "0 6 * * *", force=False)
    assert tmp_path / ".github/dashboard/dashboard_watch.py" in written
    watching.load_watch_list((tmp_path / "watchlist.yaml").read_text(encoding="utf-8"))
    workflow = yaml.safe_load((tmp_path / ".github/workflows/radar.yml").read_text(encoding="utf-8"))
    assert workflow[True]["schedule"] == [{"cron": "0 6 * * *"}]
    steps = workflow["jobs"]["build"]["steps"]
    build = next(s for s in steps if "watch" in str(s.get("run", "")))
    assert build["env"]["GH_TOKEN"] == "${{ secrets.RADAR_TOKEN || github.token }}"
    assert "git push --force origin dashboard" in steps[-1]["run"]
    with pytest.raises(FileExistsError):
        dashboard.init_watch(tmp_path, "0 6 * * *", force=False)


def test_the_watch_actions_publish_step_keeps_only_the_pages(tmp_path: Path) -> None:
    """Run the Action's last step against a local repo standing in for GitHub."""
    remote, work, site = tmp_path / "remote.git", tmp_path / "work", tmp_path / "site"
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True, capture_output=True)
    dashboard.init_watch(work, "0 6 * * *", force=False)
    subprocess.run([*git, "add", "-A"], cwd=work, check=True)
    subprocess.run([*git, "commit", "-qm", "setup"], cwd=work, check=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=work, check=True)
    (work / ".github/dashboard/__pycache__").mkdir()  # running the scripts leaves this behind
    (work / ".github/dashboard/__pycache__/x.pyc").write_text("x")
    site.mkdir()
    (site / "index.html").write_text("<p>overview</p>")
    (site / "a__one.html").write_text("<p>one</p>")
    workflow = yaml.safe_load((work / ".github/workflows/radar.yml").read_text(encoding="utf-8"))
    step = workflow["jobs"]["build"]["steps"][-1]["run"]
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "RUNNER_TEMP": str(tmp_path),
           "HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1"}
    result = subprocess.run(["bash", "-e", "-c", step], cwd=work, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    files = subprocess.run(
        ["git", "ls-tree", "--name-only", "dashboard"], cwd=remote, capture_output=True, text=True
    ).stdout.split()
    assert files == ["a__one.html", "index.html"]
