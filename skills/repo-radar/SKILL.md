---
name: repo-radar
description: repo-radar. Build a one-page HTML dashboard of a GitHub repo (open pull requests sorted by what they need, open issues by whether anyone is on them, a graph of how PRs, issues and plan boxes link, and recently closed work by release), set it up to rebuild every day with a GitHub Action, watch several repos at once from a watch list with an overview page, and compare a team's plan file with GitHub. Use when someone wants a status dashboard or morning view of a repo or of several repos, asks "where are we", "where am I", "how are my teams' repos doing", "what is left in my section", "what needs review", "is my PR on the plan", wants their PR put on the plan, or runs the weekly plan refresh.
---

# repo-radar

The dashboard is one HTML file, drawn from GitHub by `scripts/dashboard.py`. It
needs Python 3.10+, PyYAML, and the GitHub CLI (`gh`), signed in. Nothing in it
calls an AI, so it can rebuild every morning in a GitHub Action for free.

Its tabs:

| Tab | What it shows |
|---|---|
| Plan | Only when the repo has a plan file. Every part of the system as boxes, who owns each, and which items are built, in review, or missing. Flags items whose PR has merged or closed, and open PRs no item points at. |
| Pull requests | Open PRs sorted by what they need: ready to merge, needs review, waiting on the author, checks failing, draft. "Start here" picks up to five. |
| Issues | Open issues: nobody on it yet, someone assigned, a PR is open. |
| Graph | How open work links: plan box → issue → PR, sub-issues, "blocked by", PRs built on other PRs' branches. |
| Done | PRs and issues closed in the last 90 days, under the release that shipped them. |

There are two ways to set it up. Ask which one the person wants if it is not clear:

| Way | For | What it adds, where |
|---|---|---|
| **In one repo** (`init`) | Someone working on that repo | A daily Action in that repo, building that repo's page |
| **Watch list** (`init --watch`) | Someone keeping an eye on several repos, like a manager or a teacher | A daily Action in one repo of their own, building a page per watched repo plus an overview. Nothing is added to the watched repos |

`SCRIPT` below means `scripts/dashboard.py` in this skill's folder, or
`.github/dashboard/dashboard.py` in a repo that has run `init`.

## The plan file (optional)

The plan lists what the system needs, which GitHub cannot know: parts nobody
has opened an issue or PR for yet. The full format is at the top of
`scripts/dashboard_plan.py`, and `templates/plan.yaml` is a starter. In short:
groups of boxes, each box a list of items, each item `built`, `simulated`, `pr`
(with its number), or `missing`. Boxes have an `owner`, or take their group's.
The default place is `docs/plan.yaml`; pass `--plan` for another path.

## Rules

1. **Report first, edit only when asked.** The script never edits the plan. Edit
   it only when the person asks you to put their pull request on it.
2. **Edit only the person's own items.** Leave other people's items and the `as_of`
   line alone. Open pull requests then do not all edit the same lines.
3. **Do not mark items `built` unless the person runs the weekly refresh.** One person
   does that once a week, after the pull request merges. Say "merged, ready for the
   weekly refresh" instead.
4. **Never invent a status.** An item is `pr` only when an open pull request does that
   work. When you cannot tell which box a pull request belongs to, ask.
5. **Never commit the HTML page to the main branch.** The daily Action keeps it on its
   own `dashboard` branch. A page you build by hand goes in a scratch folder.

## Set it up in a repo

Ask, in one go, before writing anything:

- Does the team want a plan? If yes, where (default `docs/plan.yaml`), and does one
  exist already? Any file in the format above works, so an existing one can stay put.
- What time should it rebuild? The Action uses UTC; default 11:00 UTC daily.

Then, from the repo's top folder:

```bash
python SCRIPT init                                   # scripts + daily Action
python SCRIPT init --with-plan                       # ... and a starter docs/plan.yaml
python SCRIPT init --plan path/to/plan.yaml          # ... using a plan that exists
```

`init` writes `.github/dashboard/` (the scripts) and `.github/workflows/dashboard.yml`,
and refuses to replace files that exist. Then:

1. Build the page once locally (next section) and show it, so the person sees it work.
2. If you wrote a starter plan, fill it in with the person: groups, boxes, owners,
   and a `people` list mapping each owner name to their GitHub login.
3. Tell them what to commit (the files `init` wrote, and the plan), and that after
   it reaches the default branch they can run it at once from the Actions tab
   ("Dashboard", then "Run workflow").
4. Tell them how to look at it each morning:
   `git fetch origin dashboard && git show origin/dashboard:index.html > dashboard.html`,
   then open `dashboard.html`. For a public repo, they can instead turn on GitHub
   Pages for the `dashboard` branch and get a web address.

If the Action fails with "Permission denied" on push, the repo or organization
limits what Actions may do: Settings → Actions → General → Workflow permissions,
"Read and write". The person, not you, changes that setting.

## Set up a watch list (several repos)

Ask, in one go: which repos to watch (as owner/name), whether any keeps its plan
somewhere other than `docs/plan.yaml`, which repo of theirs should hold the watch
list (a new empty repo is fine), and what time to rebuild (UTC).

Before writing anything, build the pages once so the person sees them:

```bash
python SCRIPT watch --list <scratch dir>/watchlist.yaml --out <scratch dir>/radar
```

Open `index.html` in that folder. A repo that cannot be read shows its error on its
row instead of stopping the others: usually a typo in the name, or a private repo.

Then, in the repo that will hold the list:

```bash
python SCRIPT init --watch            # scripts, watchlist.yaml, and .github/workflows/radar.yml
```

Write the person's repos into `watchlist.yaml`, then tell them:

1. What to commit (the files `init --watch` wrote), and that once it reaches the
   default branch they can run it at once from the Actions tab ("Radar", then "Run workflow").
2. **Private repos need a token.** The Action can read public repos and its own repo,
   nothing else. To watch private repos, the person creates a GitHub token that can
   read them, and saves it as a secret named `RADAR_TOKEN` in the watching repo
   (Settings → Secrets and variables → Actions). They do this themselves; never ask
   for the token or paste it anywhere.
3. How to look at it each morning:
   `mkdir -p radar && git fetch origin dashboard && git archive origin/dashboard | tar -x -C radar`,
   then open `radar/index.html`.

To add or remove a repo later, edit `watchlist.yaml`; nothing else changes.

## Look at it now

```bash
python SCRIPT build --out <scratch dir>/dashboard.html
```

Run it inside the repo (or pass `--repo owner/name`). Write the page to your
scratchpad or another folder outside git, then show it to the person. Explain what
it says in plain words, starting with the "Start here" card and any yellow tags on
the Plan tab. Every count carries its grain: "12 of 16 open pull requests need
review", not "12 need review".

## Where am I (one person, against the plan)

You need two names: the **owner name** as the plan writes it, and the **GitHub login**.
If the plan's `people` list has the login `gh` is signed in as, the script finds the
name itself. Otherwise ask, and pass `--owner "<Name>"`. Pass `--login` only when the
person asks about someone else.

Run it twice when the person is on a pull request branch. Main shows what the team
sees today; the branch shows what this pull request will change:

```bash
git fetch origin
python SCRIPT me --ref origin/main
python SCRIPT me
```

The report has four tables:

| Table | What it tells the person |
|---|---|
| Your boxes | For each box they own or have a pull request in: how many items are built, simulated, in a PR, missing |
| Items still missing | Their next work, box by box |
| Items marked pr, checked against GitHub | An open PR needs nothing. A merged PR is ready for the weekly refresh. A closed, unmerged PR means the item should go back to `missing` |
| Your open pull requests with no item on the plan | Work the plan does not show yet |

Explain it in this order: what is done and in review; which pull requests the plan
is missing, and which box each likely belongs to; any item whose pull request closed
without merging; the first missing item as the likely next task.

## Put a pull request on the plan (only when asked)

Work on the person's pull request branch, not on main.

1. Find the pull request number: `gh pr view --json number,title`.
2. Find the item that pull request builds. Read the person's boxes in the plan.
   - If an item already describes the work, change its status to `pr` and add `pr: <number>`.
   - If no item does, add one to the right box: `{status: pr, pr: <number>, text: "<what it builds>"}`.
     Keep `text` short and plain. Ask the person which box, when it is not obvious.
3. Check the plan still loads: `python SCRIPT build --out <scratch dir>/check.html`.
   It stops with a message naming the mistake if not.
4. Run `me` again. The pull request should now be under "Items marked pr", not under
   "no item on the plan".
5. Commit the plan file in the person's pull request.

## Weekly refresh (only for the person who does it)

Build the page on main, or run `me --ref origin/main` once for each owner. Then, in one
pull request:

- Mark each item whose pull request merged as `built`, or `simulated` if the merged
  work is a stub, fake, or skeleton. The Plan tab tags these "merged".
- Set each item whose pull request closed without merging back to `missing`.
- List the open pull requests with no item (the Plan tab's last section) in the pull
  request description, for their owners to place. Do not guess their boxes.
- Set `as_of` to the main commit and date you checked against.

## Without network access

`python SCRIPT fetch --out data.json` saves what GitHub said; `build --data data.json`
and `me --data data.json` then work offline. Tests use this.
