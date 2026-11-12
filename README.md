# repo-dashboard

A one-page HTML dashboard of a GitHub repo, rebuilt every morning. Open it and see
what needs a person today, how the open work links up, and, if your team keeps a
plan, which parts of the system are built, in review, or not started.

It is a [Claude Code](https://claude.com/claude-code) skill, plus a small Python
script that does the actual work. The skill sets the dashboard up in your repo and
explains it; the script draws the page, so the daily rebuild runs in a GitHub Action
with no AI and no API key.

![The Plan tab of a made-up project](docs/screenshot-plan.png)

![The Graph tab, in dark mode](docs/screenshot-graph.png)

*Both pictures show Pantry Planner, a made-up project in `examples/demo/`.*

## What is on the page

| Tab | What it shows |
|---|---|
| **Plan** | Only if your repo has a plan file. Every part of the system as a box, who owns it, and each item's status: built, a stub, in a pull request, or missing. A yellow tag marks an item whose pull request has merged or closed, so the plan needs updating. Open pull requests that no item points at are listed at the end. |
| **Pull requests** | Open pull requests, sorted by what they need: ready to merge, needs review, waiting on the author, checks failing, draft. A "Start here" card picks up to five. |
| **Issues** | Open issues: nobody on it yet, someone assigned, a pull request open. |
| **Graph** | How the open work links: plan box → issue → pull request, sub-issues, "blocked by", and pull requests built on another's branch. |
| **Done** | Pull requests and issues closed in the last 90 days, under the release that shipped them (or the month, if the repo has no releases). |

The page is one file with nothing loaded from the internet. It has a search box,
dark mode, and a print layout. Every number and title links to GitHub.

## Install

You need Python 3.10 or newer, PyYAML (`pip install pyyaml`), and the
[GitHub CLI](https://cli.github.com/) (`gh`), signed in.

**As a Claude Code plugin.** In Claude Code:

```
/plugin install repo-dashboard --marketplace sv642-hub/repo-dashboard
```

Then ask Claude, in your project: "set up the repo dashboard".

**Or copy the skill.** Copy `skills/repo-dashboard/` into your repo's
`.claude/skills/` (for everyone on the repo) or `~/.claude/skills/` (just you).

**Or skip Claude entirely.** The script works on its own:

```bash
python skills/repo-dashboard/scripts/dashboard.py build --out dashboard.html
```

## Set it up to rebuild every day

From your repo's top folder:

```bash
python <path to>/skills/repo-dashboard/scripts/dashboard.py init
```

This writes the scripts to `.github/dashboard/` and a GitHub Action to
`.github/workflows/dashboard.yml`. Add `--with-plan` for a starter plan in
`docs/plan.yaml`, or `--plan path/to/plan.yaml` to use a plan you already have.
Commit those files. Once they reach your default branch, the Action runs every day
at 11:00 UTC (change it with `--cron`), and you can run it at once from the Actions
tab.

The Action keeps the page on a branch called `dashboard`. It holds one commit,
replaced each day, so old pages do not pile up. To open today's page:

```bash
git fetch origin dashboard && git show origin/dashboard:index.html > dashboard.html
```

then open `dashboard.html` in a browser. For a public repo, you can instead turn on
GitHub Pages for the `dashboard` branch and get a web address. (Pages on a private
repo needs a paid plan and may make the page public, so the branch is the default.)

## The plan file

The plan is optional. It is for what GitHub cannot know: the parts of the system
nobody has opened an issue or a pull request for yet.

```yaml
title: "Pantry Planner: what is built"
as_of: "main at 1a2b3c4, checked 2026-11-05"
people:                      # owner name -> GitHub login
  Ana Lee: ana-lee
groups:
  app:
    title: App
    owner: Ana Lee           # owns every box in the group, unless a box says otherwise
    boxes:
      - title: Shopping list
        items:
          - {status: built, text: "Make a list from what is running low"}
          - {status: pr, pr: 41, text: "Share a list by link", issue: 13}
          - {status: missing, text: "Sort by aisle"}
```

Statuses: `built` (merged and working), `simulated` (merged, but a stub or fake),
`pr` (in an open pull request, with its number), `missing`. The full format is at the
top of [`dashboard_plan.py`](skills/repo-dashboard/scripts/dashboard_plan.py).

How a team keeps it current: each pull request marks only its own items `pr`, so
open pull requests do not edit the same lines. Once a week, one person marks merged
items `built` (the dashboard flags them) and sets `as_of`.

## Commands

| Command | What it does |
|---|---|
| `dashboard.py build --out page.html` | Ask GitHub, then draw the page |
| `dashboard.py fetch --out data.json` | Only ask GitHub, and save what it said |
| `dashboard.py build --data data.json --out page.html` | Draw from a saved file, offline |
| `dashboard.py me` | One person's plan items, checked against their pull requests |
| `dashboard.py init` | Add the scripts and the daily Action to a repo |

Each takes `--help`.

## Why not a GitHub project board?

We like GitHub's project boards, and if your team already keeps one up to date, keep
it. We built this because we needed two things a board did not give us:

- **The parts nobody has started.** A board shows issues and pull requests. Our plan
  also lists the parts of the system that do not have an issue yet, with an owner.
- **No upkeep.** A board needs someone to add cards and move them. This page is
  rebuilt from GitHub every morning, sorted so the first thing to do is at the top.

It deliberately stops there: the page only reads. No assigning, no sprints, no
dragging cards.

## How it sorts things (no AI)

- **Pull requests:** draft → checks failing → changes requested → approved → anything
  else needs review. The first rule that fits wins.
- **Issues:** has an open pull request that closes it → assigned → nobody on it.
- **Graph links:** only links GitHub or the plan records ("Closes #12" in a pull
  request, sub-issues, "blocked by", a pull request opened on another's branch, a
  plan item naming a PR or issue). Closed work is left out.

## Development

```bash
uv run pytest
```

The tests use `examples/demo/data.json`, made by `examples/make_demo_data.py`, so
they need no network.

## Credits

This grew out of a status diagram a course team kept for their project. The plan
checks and the "where am I" report come from a Claude Code skill by Verness Chin.
The idea of a daily triage page came from the dashboard built for
[mcp-gateway-registry](https://github.com/agentic-community/mcp-gateway-registry).

## License

[MIT](LICENSE)
