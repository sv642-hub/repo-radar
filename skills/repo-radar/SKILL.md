---
name: repo-radar
description: repo-radar. Build a one-page HTML dashboard of a GitHub repo (open pull requests sorted by what they need, open issues by whether anyone is on them, a graph of how PRs, issues and plan boxes link, and recently closed work by release), set it up to rebuild every day with a GitHub Action, watch several repos at once from a watch list with an overview page, compare a team's plan file with GitHub, write plain AI summaries of what each commit and merged PR changed, and draft a first plan from a repo's history. Use when someone wants a status dashboard or morning view of a repo or of several repos, asks "where are we", "where am I", "how are my teams' repos doing", "what is left in my section", "what needs review", "is my PR on the plan", wants their PR put on the plan, runs the weekly plan refresh, wants better titles for commits ("what did each commit do"), or has no plan and wants one drafted.
---

# repo-radar

The dashboard is one HTML file, drawn from GitHub by `scripts/dashboard.py`. It
needs Python 3.10+, PyYAML, and the GitHub CLI (`gh`), signed in. The scripts never
call an AI, so the page can rebuild every morning in a GitHub Action for free. Two
optional steps use you, the AI, and only when the person asks: writing summaries of
what commits and pull requests changed, and drafting a first plan. Both save files the
scripts then read.

Its tabs:

| Tab | What it shows |
|---|---|
| Plan | Only when the repo has a plan file. Every part of the system as boxes, who owns each, and which items are built, in review, or missing. Flags items whose PR has merged or closed, and open PRs no item points at. |
| Pull requests | Open PRs sorted by what they need: ready to merge, needs review, waiting on the author, checks failing, draft. "Start here" picks up to five. |
| Issues | Open issues: nobody on it yet, someone assigned, a PR is open. |
| Graph | How open work links: plan box → issue → PR, sub-issues, "blocked by", PRs built on other PRs' branches. |
| Done | PRs and issues closed in the last 90 days, and commits pushed straight to the main branch with no PR, under the release that shipped them. |

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
   own `dashboard` branch. A page you build by hand goes in a temporary folder outside
   the repo (`<scratch dir>` below).

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

## Update a repo's copy of the scripts

`init` copies the scripts into the repo, so a repo keeps running the version it got
until someone updates it. When the person asks to update repo-radar in a repo, or
this skill's scripts are newer than the repo's, run from the repo's top folder:

```bash
python scripts/dashboard.py update        # this skill's copy, not .github/dashboard/'s
```

It replaces only the scripts in `.github/dashboard/` and says which changed. The
Action, the watch list, and the plan stay as the person left them. Then tell them to
commit `.github/dashboard/`.

## Look at it now

```bash
python SCRIPT build --out <scratch dir>/dashboard.html
```

Run it inside the repo (or pass `--repo owner/name`). Write the page to a temporary
folder outside the repo, so it never gets committed, then show it to the person. Explain what
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

## Write summaries of what each commit changed (only when asked)

Commit messages like "fix" or "wip" say little. You read what each commit pushed
straight to main, and each merged pull request, actually changed, and write one plain
line about it, then a short digest of all of them grouped by topic. The Done tab
opens with the digest ("What changed"), and shows each line, marked "AI summary",
above the commit's original message. Each commit is read once and saved, so the next
run only does new ones.

1. From the repo's top folder, list what has no summary yet:
   `python SCRIPT summarize --todo > <scratch dir>/todo.json`. Each entry has a
   `read` command that shows its changes.
2. Say how many there are. If there are more than 40, ask before reading them all,
   or offer to do the newest 40 first.
3. For each one, run its `read` command and read the change. For a big change, start
   with the list of files (`git show --stat`, `gh pr diff --name-only`) and read the
   parts that matter.
4. Write one line, under 120 characters, in the present tense, saying what the change
   does, in words a teammate who did not write it would understand: "Adds a retry with
   backoff when sync fails", not "Update sync.py". Say only what the change shows. Do
   not guess why, and never copy secrets, keys, or personal data into a line.
5. Write the **digest**: what all of the summarized changes (this run's and earlier
   ones still in the Done tab) did, grouped by topic, not by date. Up to 8 groups,
   each a short title ("New tools, all off by default") and 2 to 6 plain lines. Say
   what changed for someone using or working on the repo; leave out commit ids.
6. Save everything in `<scratch dir>/new.json`:

   ```json
   {"commits": {"<full commit id>": "<line>"}, "prs": {"<number>": "<line>"},
    "digest": {"written": "<YYYY-MM-DD>", "covers": "<e.g. the last 40 commits, up to 445641b>",
               "groups": [{"title": "<topic>", "items": ["<line>", "<line>"]}]}}
   ```

   then run `python SCRIPT summarize --add <scratch dir>/new.json`. It checks every
   line and writes `.github/dashboard/summaries.yaml`; a new digest replaces the old
   one. Never edit that file's ids by hand.
7. Build the page (Look at it now) and show it: the digest is at the top of the Done
   tab. In the terminal, give the digest too, then name the summaries that are only
   your reading because the commit message said little, and how many older commits
   still have none.
8. Tell the person to commit `.github/dashboard/summaries.yaml` the way their team
   commits anything else; the daily Action shows it from then on. A watch list reads
   it from each watched repo too.

If a line is wrong, the person fixes the text in the file by hand.

## Draft a plan from the history (only when asked, for a repo with no plan)

A plan normally takes a person an afternoon to write. You can draft one from what the
repo already shows, for the team to fix and keep. It is a draft: never commit it.

1. Read what is there: the README and docs, the folder layout, the merged pull
   requests (`gh pr list --state merged --limit 200 --json number,title,files`), the
   commits (`git log --stat --since="6 months ago"`), the open pull requests and
   issues, and `.github/dashboard/summaries.yaml` if it exists.
2. Make **groups** for the main parts of the system (often top folders, such as the
   app, the API, the data pipeline), **boxes** for the pieces inside each, and
   **items** for what each piece does.
3. Give each item the status the repo shows, and nothing more:
   - `built`: the code is on main and does it.
   - `simulated`: on main, but a stub, a fake, or a placeholder (raises "not
     implemented", returns fixed data).
   - `pr` with its number: an open pull request does it.
   - `missing`: only when the repo itself says it is planned: an open issue (give its
     number as `issue`), a TODO, or a roadmap in the docs. Never invent missing work.
4. Set every `owner` to `null`. Do not decide who owns what. Tell the person who has
   done the most work in each area, as a suggestion, and leave `people` out.
5. Put a comment at the top: `# Draft written by AI from the repo's history on
   <date>. Check every item, add what is missing, and set owners before committing.`
   Set `as_of` to `"main at <short commit id>, drafted <date>"`.
6. Write it to `docs/plan.yaml` (or where the person says), and check that it loads:
   `python SCRIPT build --out <scratch dir>/dashboard.html`. Fix any error it names.
7. Show the page, and tell the person in plain words: how many groups, boxes and
   items, and what you were unsure of.
8. **Ask what is still to build.** A repo rarely writes down its plans, so a draft
   often has no `missing` items, and the plan's most useful part is empty. List the
   groups and boxes, and ask: "What does the team still need to build, or plan to,
   that the repo does not show yet?" Add each answer as a `missing` item in the box
   it belongs to; ask which box when it is not clear. Ask too whether they want to set
   owners now: if they name them, set each `owner` and add the `people` list
   (owner name → GitHub login). Then check it loads again (step 6) and show the page.
9. Tell them it is still a draft: the team should check it and commit it themselves.

## Without network access

`python SCRIPT fetch --out data.json` saves what GitHub said; `build --data data.json`
and `me --data data.json` then work offline. Tests use this.
