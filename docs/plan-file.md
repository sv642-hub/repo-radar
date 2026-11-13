# The plan file

The plan is optional. It holds what GitHub cannot know: the parts of the system
nobody has started.

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

Each item is `built`, `simulated` (merged, but a stub or fake), `pr` (with its
number), or `missing`. The full format is at the top of
[`dashboard_plan.py`](../skills/repo-radar/scripts/dashboard_plan.py).

To keep it current without merge fights: each pull request updates only its own items,
and once a week one person marks what merged (the page flags those) and sets `as_of`.
