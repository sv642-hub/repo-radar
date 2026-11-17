# Let the AI help

The page itself never calls an AI: the daily rebuild is plain Python, free, and the
same every time. Two optional steps use the AI you already work with (Claude Code or
Codex), only when you ask, and save files the page reads from then on.

## Summaries of what each commit changed

Commit messages like "fix" or "wip" do not say much. Ask:

> summarize the commits for repo-radar

The skill reads what each commit pushed straight to main, and each merged pull
request, really changed, and writes one plain line for each, such as "Shows an
empty-list message instead of crashing when a list has no items". They are saved in
`.github/dashboard/summaries.yaml`. Each commit is read once, so later runs only do
the new ones.

It also writes a short digest of all of them, grouped by topic ("New tools, all off
by default", "Fixes", and so on). The Done tab opens with that digest, under **What
changed**, and shows each commit's line with a dashed **AI summary** tag and the
original message under it. The AI can be wrong; fix a line by editing the file. A watch list
reads each watched repo's file too.

The commands behind it, if you want to run them yourself:

```bash
python .github/dashboard/dashboard.py summarize --todo     # what has no summary yet, and how to read each
python .github/dashboard/dashboard.py summarize --add new.json
```

`new.json` looks like `{"commits": {"<full commit id>": "<line>"}, "prs": {"12": "<line>"}, "digest": {...}}`;
the format is at the top of [`dashboard_summaries.py`](../skills/repo-radar/scripts/dashboard_summaries.py).

## A first plan, drafted from the history

No plan yet? Ask:

> draft a plan for repo-radar from the history

The skill reads the README, the folders, the merged and open pull requests, the
commits, and the open issues, and writes a draft `docs/plan.yaml`: the parts of the
system as boxes, each item marked built, a stub, or in an open pull request. It marks
something missing only when the repo says it is planned (an open issue, a TODO, a
roadmap), and leaves every owner empty. Then it shows you the draft and asks what is
still to build, since most repos never write that down, and adds your answers as
missing items. If you name owners, it sets them too.

It never commits the draft. Check it with your team, add the parts still to build,
set owners, then commit it. The Plan tab appears on the next rebuild.
