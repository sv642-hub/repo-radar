"""The command line: build, me, and init, run the way a person or the Action runs them."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from conftest import DEMO, PLAN, PRS, SCRIPTS

import dashboard

SCRIPT = SCRIPTS / "dashboard.py"


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def saved(tmp_path: Path) -> Path:
    """A folder with the test plan and its GitHub data saved, as fetch would save it."""
    (tmp_path / "plan.yaml").write_text(yaml.safe_dump(PLAN), encoding="utf-8")
    data = {
        "repo": "o/r",
        "url": "https://github.com/o/r",
        "fetched_at": "2026-11-12T08:00:00Z",
        "days": 90,
        "open_prs": [p for p in PRS if p["state"] == "OPEN"],
        "closed_prs": [p for p in PRS if p["state"] != "OPEN"],
        "open_issues": [],
        "closed_issues": [],
        "releases": [],
        "other_prs": [],
    }
    (tmp_path / "data.json").write_text(json.dumps(data), encoding="utf-8")
    return tmp_path


def test_build_writes_the_page(tmp_path: Path) -> None:
    out = tmp_path / "out" / "dashboard.html"
    result = _run(tmp_path, "build", "--data", str(DEMO / "data.json"), "--plan", str(DEMO / "plan.yaml"), "--out", str(out))
    assert result.returncode == 0, result.stderr
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_build_finds_docs_plan_yaml_by_itself(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    shutil.copyfile(DEMO / "plan.yaml", tmp_path / "docs" / "plan.yaml")
    result = _run(tmp_path, "build", "--data", str(DEMO / "data.json"), "--out", "d.html")
    assert result.returncode == 0, result.stderr
    assert 'data-tab="plan"' in (tmp_path / "d.html").read_text(encoding="utf-8")


def test_build_stops_on_a_bad_plan_and_names_the_mistake(tmp_path: Path) -> None:
    (tmp_path / "plan.yaml").write_text("title: x\ngroups: {}\n", encoding="utf-8")
    result = _run(tmp_path, "build", "--data", str(DEMO / "data.json"), "--plan", "plan.yaml", "--out", "d.html")
    assert result.returncode == 1
    assert "plan.yaml: missing top-level key 'groups'" in result.stderr
    assert not (tmp_path / "d.html").exists()


def test_me_prints_the_report_and_finds_the_name_from_people(saved: Path) -> None:
    result = _run(saved, "me", "--plan", "plan.yaml", "--data", "data.json", "--login", "ana")
    assert result.returncode == 0, result.stderr
    assert "# Plan status for Ana Lee (@ana)" in result.stdout
    assert "| #5 | PR 5 |" in result.stdout


def test_me_fails_clearly_for_someone_not_on_the_plan(saved: Path) -> None:
    result = _run(saved, "me", "--plan", "plan.yaml", "--data", "data.json", "--login", "cy")
    assert result.returncode == 1
    assert "@cy is not in the plan's people list" in result.stderr
    result = _run(saved, "me", "--plan", "plan.yaml", "--data", "data.json", "--login", "cy", "--owner", "Cy Park")
    assert result.returncode == 1
    assert "no item belongs to 'Cy Park'" in result.stderr


def test_me_does_not_edit_the_plan(saved: Path) -> None:
    _run(saved, "me", "--plan", "plan.yaml", "--data", "data.json", "--login", "ana")
    assert yaml.safe_load((saved / "plan.yaml").read_text(encoding="utf-8")) == PLAN


def test_init_writes_the_scripts_the_action_and_a_starter_plan(tmp_path: Path) -> None:
    written = dashboard.init(tmp_path, None, with_plan=True, cron="0 6 * * 1-5", force=False)
    assert tmp_path / ".github/dashboard/dashboard.py" in written
    assert (tmp_path / "docs/plan.yaml").exists()
    workflow = yaml.safe_load((tmp_path / ".github/workflows/dashboard.yml").read_text(encoding="utf-8"))
    assert workflow[True]["schedule"] == [{"cron": "0 6 * * 1-5"}]  # YAML reads the key `on` as True
    steps = " ".join(str(step.get("run", "")) for step in workflow["jobs"]["build"]["steps"])
    assert ".github/dashboard/dashboard.py build" in steps
    assert "--plan" not in steps  # docs/plan.yaml is found without it
    assert "git push --force origin dashboard" in steps


def test_init_passes_a_plan_in_another_place_to_the_action(tmp_path: Path) -> None:
    dashboard.init(tmp_path, Path("docs/img/architecture.yaml"), with_plan=False, cron="0 11 * * *", force=False)
    text = (tmp_path / ".github/workflows/dashboard.yml").read_text(encoding="utf-8")
    assert "--plan docs/img/architecture.yaml" in text
    assert not (tmp_path / "docs").exists()


def test_init_refuses_to_replace_files_and_writes_nothing_then(tmp_path: Path) -> None:
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/dashboard.yml").write_text("mine", encoding="utf-8")
    with pytest.raises(FileExistsError):
        dashboard.init(tmp_path, None, with_plan=False, cron="0 11 * * *", force=False)
    assert not (tmp_path / ".github/dashboard").exists()
    assert (tmp_path / ".github/workflows/dashboard.yml").read_text(encoding="utf-8") == "mine"


def test_the_installed_copy_runs_on_its_own(tmp_path: Path) -> None:
    dashboard.init(tmp_path, None, with_plan=True, cron="0 11 * * *", force=False)
    installed = tmp_path / ".github/dashboard/dashboard.py"
    result = subprocess.run(
        [sys.executable, str(installed), "build", "--data", str(DEMO / "data.json"), "--out", "d.html"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "My project: what is built" in (tmp_path / "d.html").read_text(encoding="utf-8")


def test_the_demo_data_file_is_current() -> None:
    sys.path.insert(0, str(DEMO.parent))
    import make_demo_data

    assert json.loads((DEMO / "data.json").read_text(encoding="utf-8")) == make_demo_data.demo()
