"""AI summaries: the file's checks, what still needs one, saving new ones, and the page."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import DEMO, SCRIPTS

import dashboard_page as page
import dashboard_summaries as summarizing

SHA = "a" * 40


def test_a_good_file_loads_with_numbers_for_prs() -> None:
    found = summarizing.load(f'commits:\n  "{SHA}": "Adds a retry"\nprs:\n  "41": "Shares a list"\n')
    assert found == {"commits": {SHA: "Adds a retry"}, "prs": {41: "Shares a list"}}
    assert summarizing.load(None) == {"commits": {}, "prs": {}}


@pytest.mark.parametrize(
    "text, message",
    [
        ("other: {}", "only `commits` and `prs`"),
        ("commits: {abc1234: x}", "full commit id"),
        ("commits: {1234567890123456789012345678901234567890: x}", "full commit id"),  # unquoted, read as a number
        (f'commits: {{"{SHA}": ""}}', "one line"),
        (f'commits: {{"{SHA}": "{"x" * 201}"}}', "under 200"),
        ("prs: {0: x}", "pull request number"),
        ("prs: {x: y}", "pull request number"),
        ("commits: [", "not valid YAML"),
    ],
)
def test_a_bad_file_is_refused_with_a_message(text: str, message: str) -> None:
    with pytest.raises(summarizing.SummariesError, match=message):
        summarizing.load(text)


def test_the_file_round_trips_and_keeps_an_all_digit_id_as_text() -> None:
    digits = "1" * 40
    text = summarizing.dump({"commits": {digits: "Adds: a colon"}, "prs": {3: "x"}})
    assert text.startswith("# What each commit")
    assert summarizing.load(text) == {"commits": {digits: "Adds: a colon"}, "prs": {3: "x"}}


def test_todo_lists_pushes_and_merged_prs_with_no_summary(demo_data: dict) -> None:
    pushes = [p["oid"] for p in demo_data["pushes"]]
    have = {"commits": {pushes[0]: "x"}, "prs": {39: "x"}}
    items = summarizing.todo(demo_data, have)
    assert [(i["kind"], i["id"]) for i in items] == [
        ("commit", pushes[1]), ("pr", 37), ("pr", 36), ("pr", 35), ("pr", 34), ("pr", 33)
    ]  # 38 closed without merging, so there is nothing to summarize
    assert items[0]["read"] == f"git show --stat --patch {pushes[1]}"
    assert items[1]["read"] == "gh pr diff 37 --repo example-org/pantry-planner"


def test_the_done_tab_shows_the_summary_marked_as_ai_with_the_original_under_it(demo_data: dict) -> None:
    oid = demo_data["pushes"][0]["oid"]
    demo_data["summaries"] = {"commits": {oid: "Fixes <the> spelling"}, "prs": {39: "Reads barcodes"}}
    html = page.render(demo_data, None)
    assert "Fixes &lt;the&gt; spelling</a> <span class=\"chip ai\"" in html
    assert "commit message: Fix a typo in the README" in html
    assert "PR title: Scan barcodes with the phone camera" in html
    assert "fixes &lt;the&gt; spelling fix a typo" in html  # search finds either
    assert html.count("AI summary</span>") == 2


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / "dashboard.py"), *args], cwd=tmp_path,
                          capture_output=True, text=True)


def test_summarize_lists_then_saves_and_build_shows_it(tmp_path: Path) -> None:
    data = str(DEMO / "data.json")
    todo = _run(tmp_path, "summarize", "--todo", "--data", data)
    assert todo.returncode == 0, todo.stderr
    first = json.loads(todo.stdout)[0]
    (tmp_path / "new.json").write_text(json.dumps({"commits": {first["id"]: "Fixes the README"}, "prs": {"39": "Scans"}}))
    added = _run(tmp_path, "summarize", "--add", "new.json")
    assert added.returncode == 0, added.stderr
    saved = summarizing.load((tmp_path / summarizing.PATH).read_text())
    assert saved == {"commits": {first["id"]: "Fixes the README"}, "prs": {39: "Scans"}}
    again = json.loads(_run(tmp_path, "summarize", "--todo", "--data", data).stdout)
    assert first["id"] not in [i["id"] for i in again] and 39 not in [i["id"] for i in again]
    built = _run(tmp_path, "build", "--data", data, "--out", "page.html")
    assert built.returncode == 0, built.stderr
    assert "Fixes the README" in (tmp_path / "page.html").read_text()


def test_summarize_refuses_bad_json_and_leaves_the_file_alone(tmp_path: Path) -> None:
    (tmp_path / "new.json").write_text('{"commits": {"abc": "x"}}')
    result = _run(tmp_path, "summarize", "--add", "new.json")
    assert result.returncode == 1 and "full commit id" in result.stderr
    assert not (tmp_path / summarizing.PATH).exists()
    (tmp_path / "new.json").write_text("{not json")
    assert "not valid JSON" in _run(tmp_path, "summarize", "--add", "new.json").stderr
