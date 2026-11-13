#!/usr/bin/env python3
"""A one-page HTML dashboard of a GitHub repo: open PRs, open issues, how they link, and the plan.

    python dashboard.py build --out dashboard.html        # ask GitHub, then draw the page
    python dashboard.py fetch --out data.json             # only ask GitHub, and save what it said
    python dashboard.py build --data data.json --out dashboard.html   # draw from a saved file
    python dashboard.py me --owner "Ana Lee"              # one person's plan items vs their PRs
    python dashboard.py init                              # add the dashboard to the repo in this folder
    python dashboard.py watch --out site/                 # one page per repo in watchlist.yaml, plus an overview
    python dashboard.py init --watch                      # make this repo watch other repos every day
    python dashboard.py update                            # refresh the scripts init installed, nothing else

Needs Python 3.10+, PyYAML, and the GitHub CLI (gh), signed in. Run it inside the
repo, or pass --repo owner/name. The plan file is optional; by default it is
docs/plan.yaml when that file exists.
"""

import argparse
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import dashboard_github as github
import dashboard_page as page
import dashboard_plan as plans
import dashboard_watch as watching

logging.basicConfig(
    level=logging.INFO,  # Set the log level to INFO
    # Define log message format
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)
logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE.parent / "templates"
SCRIPTS = [
    "dashboard.py",
    "dashboard_github.py",
    "dashboard_graph.py",
    "dashboard_page.py",
    "dashboard_plan.py",
    "dashboard_watch.py",
]
DEFAULT_PLAN = Path("docs/plan.yaml")
INSTALL_DIR = Path(".github/dashboard")
WORKFLOW = Path(".github/workflows/dashboard.yml")
WATCH_WORKFLOW = Path(".github/workflows/radar.yml")
WATCH_LIST = Path("watchlist.yaml")


def read_plan(path: Path | None, ref: str | None = None) -> dict[str, Any] | None:
    """The plan from --plan, else docs/plan.yaml if it exists, else None (no plan).

    With ref (such as origin/main), the plan is read from that git commit instead
    of from the files on disk.
    """
    if path is None:
        if ref is None and not DEFAULT_PLAN.exists():
            return None
        path = DEFAULT_PLAN
    if ref is None:
        if not path.exists():
            raise plans.PlanError(f"{path}: no such file")
        text = path.read_text(encoding="utf-8")
    else:
        result = subprocess.run(
            ["git", "show", f"{ref}:{path.as_posix()}"], capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            raise plans.PlanError(f"{path} at {ref}: {result.stderr.strip()}")
        text = result.stdout
    return plans.load_plan(text, str(path))


def get_data(args: argparse.Namespace, plan: dict[str, Any] | None) -> dict[str, Any]:
    """GitHub's data: from --data when given, else fetched now through gh."""
    if args.data:
        return json.loads(args.data.read_text(encoding="utf-8"))
    extra = plans.plan_prs(plan) if plan else set()
    return github.fetch(args.repo, args.days, args.limit, extra)


def cmd_fetch(args: argparse.Namespace) -> None:
    """Save GitHub's data to a file, so build can draw it later or offline."""
    data = get_data(args, read_plan(args.plan))
    args.out.write_text(json.dumps(data, indent=1), encoding="utf-8")
    logger.info(f"wrote {args.out}")


def cmd_build(args: argparse.Namespace) -> None:
    """Draw the page."""
    plan = read_plan(args.plan)
    html = page.render(get_data(args, plan), plan)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    logger.info(f"wrote {args.out}")


def cmd_me(args: argparse.Namespace) -> None:
    """Print one person's plan items, checked against their pull requests."""
    plan = read_plan(args.plan, args.ref)
    if plan is None:
        logger.error(f"no plan: pass --plan, or create {DEFAULT_PLAN}")
        sys.exit(1)
    data = get_data(args, plan)
    login = args.login or subprocess.run(
        ["gh", "api", "user", "-q", ".login"], capture_output=True, text=True, check=True
    ).stdout.strip()
    owner = args.owner or plans.owner_for_login(plan, login)
    if owner is None:
        logger.error(f"@{login} is not in the plan's people list; pass --owner \"Your Name\"")
        sys.exit(1)
    prs = github.all_prs(data)
    my_prs = {n for n, pr in prs.items() if pr["author"]["login"] == login}
    rows = plans.owned_items(plan, owner, my_prs)
    if not rows:
        logger.error(f"no item belongs to {owner!r} or to @{login}'s pull requests")
        sys.exit(1)
    findings = plans.check_items(rows, prs)
    unplaced = plans.unplaced_prs(plan, data["open_prs"], login)
    sys.stdout.write(plans.report(plan, owner, login, rows, findings, unplaced))


def init(repo_dir: Path, plan: Path | None, with_plan: bool, cron: str, force: bool) -> list[Path]:
    """Add the dashboard to a repo: the scripts, a daily GitHub Action, and maybe a starter plan.

    Args:
        repo_dir: The repo's top folder.
        plan: Where the plan lives, relative to repo_dir; None means docs/plan.yaml.
        with_plan: Also write a starter plan there.
        cron: When the Action runs, in cron syntax, in UTC.
        force: Replace files that already exist.

    Returns:
        The files written.

    Raises:
        FileExistsError: if a file exists and force is False. Nothing is written then.
    """
    plan_path = plan or DEFAULT_PLAN
    workflow = (TEMPLATES / "dashboard.yml").read_text(encoding="utf-8")
    plan_args = f" --plan {plan_path.as_posix()}" if plan else ""
    workflow = workflow.replace("__CRON__", cron).replace("__PLAN_ARGS__", plan_args)
    texts = {repo_dir / WORKFLOW: workflow}
    if with_plan:
        texts[repo_dir / plan_path] = (TEMPLATES / "plan.yaml").read_text(encoding="utf-8")
    return _install(repo_dir, texts, force)


def init_watch(repo_dir: Path, cron: str, force: bool) -> list[Path]:
    """Set up a repo that watches other repos: the scripts, a starter watch list, and its Action.

    Nothing is added to the watched repos. Raises FileExistsError like init.
    """
    workflow = (TEMPLATES / "radar.yml").read_text(encoding="utf-8").replace("__CRON__", cron)
    texts = {
        repo_dir / WATCH_WORKFLOW: workflow,
        repo_dir / WATCH_LIST: (TEMPLATES / "watchlist.yaml").read_text(encoding="utf-8"),
    }
    return _install(repo_dir, texts, force)


def _install(repo_dir: Path, texts: dict[Path, str], force: bool) -> list[Path]:
    """Copy the scripts into the repo and write the given files; refuse to replace any first."""
    targets = {repo_dir / INSTALL_DIR / name: HERE / name for name in SCRIPTS}
    existing = [p for p in [*targets, *texts] if p.exists()]
    if existing and not force:
        raise FileExistsError(f"already there (pass --force to replace): {[str(p) for p in existing]}")
    for target, source in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for target, text in texts.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return [*targets, *texts]


def update(repo_dir: Path) -> dict[str, list[str]]:
    """Refresh the scripts a repo got from init, with this copy's.

    Only the scripts in .github/dashboard/ change. The Action, the watch list, and the
    plan stay as they are, since the person may have edited them. A script this copy
    has and the repo does not (added in a newer version) is added.

    Returns:
        Script names, under "updated", "added", and "unchanged".

    Raises:
        FileNotFoundError: if the repo has not run init.
        ValueError: if this is the repo's own installed copy, which cannot update itself.
    """
    target = repo_dir / INSTALL_DIR
    if not (target / "dashboard.py").exists():
        raise FileNotFoundError(f"{target} has no dashboard.py; run init first")
    if target.resolve() == HERE:
        raise ValueError("this is the installed copy; run update from the skill's own scripts folder")
    result: dict[str, list[str]] = {"updated": [], "added": [], "unchanged": []}
    for name in SCRIPTS:
        new, old = HERE / name, target / name
        if not old.exists():
            result["added"].append(name)
        elif old.read_bytes() != new.read_bytes():
            result["updated"].append(name)
        else:
            result["unchanged"].append(name)
            continue
        shutil.copyfile(new, old)
    return result


def cmd_update(args: argparse.Namespace) -> None:
    result = update(args.repo_dir)
    for kind in ("updated", "added", "unchanged"):
        if result[kind]:
            logger.info(f"{kind}: {', '.join(result[kind])}")
    if result["updated"] or result["added"]:
        logger.info(f"commit {args.repo_dir / INSTALL_DIR} to use them in the daily Action")


def cmd_init(args: argparse.Namespace) -> None:
    if args.watch:
        written = init_watch(args.repo_dir, args.cron, args.force)
    else:
        written = init(args.repo_dir, args.plan, args.with_plan, args.cron, args.force)
    for path in written:
        logger.info(f"wrote {path}")


def cmd_watch(args: argparse.Namespace) -> None:
    """Build one page per repo on the watch list, and an overview page linking them."""
    entries = watching.load_watch_list(args.list.read_text(encoding="utf-8"), str(args.list))
    if args.data_dir:  # saved data, for tests and offline use: owner__name.json (+ .plan.yaml)

        def get_plan(repo: str, _: str) -> str | None:
            path = args.data_dir / watching.page_name(repo).replace(".html", ".plan.yaml")
            return path.read_text(encoding="utf-8") if path.exists() else None

        def get_data(repo: str, _: set[int]) -> dict[str, Any]:
            path = args.data_dir / watching.page_name(repo).replace(".html", ".json")
            if not path.exists():
                raise RuntimeError(f"no saved data at {path}")
            return json.loads(path.read_text(encoding="utf-8"))

    else:
        get_plan = github.read_file

        def get_data(repo: str, extra: set[int]) -> dict[str, Any]:
            return github.fetch(repo, args.days, args.limit, extra)

    pages, rows = watching.watch(
        entries, get_plan, get_data, lambda data, plan: page.render(data, plan, back="index.html")
    )
    args.out.mkdir(parents=True, exist_ok=True)
    for name, html in pages.items():
        (args.out / name).write_text(html, encoding="utf-8")
    fetched = [r["fetched_at"] for r in rows if not r.get("error")]
    built_at = max(fetched) if fetched else watching.now_stamp()
    (args.out / "index.html").write_text(page.render_index(rows, built_at), encoding="utf-8")
    failed = [r["repo"] for r in rows if r.get("error")]
    logger.info(f"wrote {len(pages)} repo pages and index.html to {args.out}")
    if failed:
        logger.warning(f"could not read: {', '.join(failed)} (the overview says why)")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def github_options(p: argparse.ArgumentParser) -> None:
        p.add_argument("--repo", help="owner/name (default: the repo in this folder)")
        p.add_argument("--plan", type=Path, help=f"the plan file (default: {DEFAULT_PLAN}, if it exists)")
        p.add_argument("--data", type=Path, help="read GitHub's data from a file saved by fetch")
        p.add_argument("--days", type=int, default=90, help="how far back the Done tab goes")
        p.add_argument("--limit", type=int, default=500, help="most PRs or issues to fetch per list")

    for name, func, help_text in [
        ("build", cmd_build, "draw the page"),
        ("fetch", cmd_fetch, "save GitHub's data to a file"),
    ]:
        p = sub.add_parser(name, help=help_text)
        github_options(p)
        p.add_argument("--out", type=Path, required=True, help="the file to write")
        p.set_defaults(func=func)

    p = sub.add_parser("me", help="one person's plan items, checked against their PRs")
    github_options(p)
    p.add_argument("--owner", help="your name as the plan writes owners (default: from people)")
    p.add_argument("--login", help="your GitHub login (default: the one gh is signed in as)")
    p.add_argument("--ref", help="read the plan at this git ref, e.g. origin/main")
    p.set_defaults(func=cmd_me)

    p = sub.add_parser("watch", help="one page per repo on a watch list, and an overview")
    p.add_argument("--list", type=Path, default=WATCH_LIST, help=f"the watch list (default: {WATCH_LIST})")
    p.add_argument("--out", type=Path, required=True, help="the folder to write the pages to")
    p.add_argument("--data-dir", type=Path, help="read saved data (owner__name.json) instead of GitHub")
    p.add_argument("--days", type=int, default=90, help="how far back the Done tab goes")
    p.add_argument("--limit", type=int, default=500, help="most PRs or issues to fetch per list")
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("init", help="add the dashboard to a repo")
    p.add_argument("--repo-dir", type=Path, default=Path("."), help="the repo's top folder")
    p.add_argument("--watch", action="store_true", help="set this repo up to watch other repos instead")
    p.add_argument("--plan", type=Path, help=f"where the plan lives (default: {DEFAULT_PLAN})")
    p.add_argument("--with-plan", action="store_true", help="also write a starter plan")
    p.add_argument("--cron", default="0 11 * * *", help="when to rebuild, in UTC (default: 11:00 daily)")
    p.add_argument("--force", action="store_true", help="replace files that already exist")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("update", help="refresh the scripts init put in a repo, nothing else")
    p.add_argument("--repo-dir", type=Path, default=Path("."), help="the repo's top folder")
    p.set_defaults(func=cmd_update)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    try:
        args.func(args)
    except (
        plans.PlanError,
        watching.WatchListError,
        FileExistsError,
        FileNotFoundError,
        RuntimeError,
        ValueError,
    ) as error:
        logger.error(str(error))
        sys.exit(1)


if __name__ == "__main__":
    main()
